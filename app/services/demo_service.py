"""The shared demo account.

The MVP is shown to people by handing out one demo login. Two consequences:

* No single person holds the account's authenticator app, so with
  DEMO_ACCOUNT_SHARED_MFA on its code prompt accepts any 6 digits.
* Everyone who tries the app leaves records behind. `reset_demo_data` puts the
  account back to the seeded demo cases, either on demand
  (`python -m scripts.reset_demo --apply`) or every
  DEMO_RESET_INTERVAL_MINUTES via `init_demo_reset`.

The reset only touches cases the demo account created and the seeded demo
cases, so it is safe next to real users' records.
"""

import fcntl
import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import or_

from app.extensions import db
from app.models.case import Case
from app.models.user import User
from app.services.retention_service import PurgeResult, RetentionService

logger = logging.getLogger(__name__)

RESET_MARKER_FILENAME = "demo_last_reset"


@dataclass
class DemoResetResult:
    cases_destroyed: List[PurgeResult] = field(default_factory=list)
    cases_seeded: int = 0


def get_demo_user(config) -> Optional[User]:
    if not config.get("DEMO_ACCOUNT_ENABLED"):
        return None
    return User.query.filter_by(email=config["DEMO_ACCOUNT_EMAIL"]).first()


def is_shared_demo_account(user: Optional[User], config) -> bool:
    """Whether this user is the demo account and it runs with shared MFA."""
    if not user or not config.get("DEMO_ACCOUNT_ENABLED"):
        return False
    if not config.get("DEMO_ACCOUNT_SHARED_MFA"):
        return False
    return (user.email or "").lower() == config["DEMO_ACCOUNT_EMAIL"].lower()


def find_resettable_cases(demo_user: User) -> List[Case]:
    """Cases the demo account created, plus the seeded demo cases."""
    from app.services.seed_service import DEMO_CASE_DEFINITIONS

    identifiers = [case_data["identifier"] for case_data in DEMO_CASE_DEFINITIONS]
    return Case.query.filter(
        or_(Case.user_id == demo_user.id, Case.identifier.in_(identifiers))
    ).all()


def reset_demo_data(config) -> DemoResetResult:
    """Destroy everything the demo account created and reseed the demo cases.

    Seeded cases are destroyed and recreated too, so edits made to them
    during a demo are undone.
    """
    from app.services.seed_service import seed_demo_cases

    result = DemoResetResult()
    demo_user = get_demo_user(config)
    if not demo_user:
        return result

    retention = RetentionService(config["UPLOAD_FOLDER"])
    for case in find_resettable_cases(demo_user):
        result.cases_destroyed.append(retention.destroy_case(case))
        # The bulk delete bypasses the session; drop the stale object so a
        # reseeded case reusing its id does not collide with it.
        db.session.expunge(case)

    before = Case.query.count()
    seed_demo_cases(demo_user)
    result.cases_seeded = Case.query.count() - before

    logger.info(
        f"Demo reset: destroyed {len(result.cases_destroyed)} case(s), "
        f"seeded {result.cases_seeded}"
    )
    return result


def init_demo_reset(app) -> None:
    """Reset the demo data on the first request after each interval elapses.

    Done lazily on a request rather than with a scheduler so it needs no cron
    entry on the demo host. The last-reset time lives in a marker file beside
    the database so every gunicorn worker sees it, and a file lock stops two
    workers resetting at once.
    """
    interval_minutes = app.config.get("DEMO_RESET_INTERVAL_MINUTES", 0)
    if interval_minutes <= 0 or not app.config.get("DEMO_ACCOUNT_ENABLED"):
        return

    interval_seconds = interval_minutes * 60
    marker_path = os.path.join(app.config["DB_DIR"], RESET_MARKER_FILENAME)

    def _is_due() -> bool:
        try:
            return time.time() - os.path.getmtime(marker_path) >= interval_seconds
        except FileNotFoundError:
            return True

    @app.before_request
    def _reset_demo_data_when_due():
        if not _is_due():
            return None

        with open(marker_path + ".lock", "w") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Another worker is resetting right now.
                return None
            try:
                if _is_due():
                    try:
                        reset_demo_data(app.config)
                    except Exception:
                        db.session.rollback()
                        logger.exception("Demo reset failed")
                    # Written even on failure so a broken reset is retried
                    # next interval rather than on every request.
                    with open(marker_path, "w") as marker:
                        marker.write(str(time.time()))
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
        return None
