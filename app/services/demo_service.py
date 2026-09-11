"""The shared demo account.

The MVP is shown to people by handing out one demo login. Two consequences:

* No single person holds the account's authenticator app, so with
  DEMO_ACCOUNT_SHARED_MFA on its code prompt accepts any 6 digits.
* Everyone who tries the app leaves records behind. `reset_demo_data` puts the
  account back to the seeded demo cases, either on demand
  (`python -m scripts.reset_demo --apply`) or nightly at DEMO_RESET_TIME
  via `init_demo_reset`.

The reset only touches cases the demo account created and the seeded demo
cases, so it is safe next to real users' records.
"""

import fcntl
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from typing import List, Optional
from zoneinfo import ZoneInfo

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


def parse_reset_time(value: str) -> dt_time:
    """Parse DEMO_RESET_TIME ("HH:MM", 24-hour)."""
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return dt_time(hour, minute)
    except ValueError:
        raise ValueError(
            f"DEMO_RESET_TIME must be HH:MM in 24-hour time, got {value!r}"
        ) from None


def most_recent_reset(now: datetime, reset_at: dt_time, tz: ZoneInfo) -> datetime:
    """The latest scheduled reset time at or before `now`."""
    local_now = now.astimezone(tz)
    scheduled = datetime.combine(local_now.date(), reset_at, tzinfo=tz)
    if scheduled > local_now:
        scheduled = datetime.combine(
            local_now.date() - timedelta(days=1), reset_at, tzinfo=tz
        )
    return scheduled


def init_demo_reset(app) -> None:
    """Reset the demo data once a night, at DEMO_RESET_TIME.

    Done lazily rather than with a scheduler so it needs no cron entry on the
    demo host: the first request after the reset time does it, before that
    request is handled. If nobody uses the app overnight, the first visitor
    next morning triggers it and still sees fresh data.

    The last-reset time lives in a marker file beside the database so every
    gunicorn worker sees it, and a file lock stops two workers resetting at
    once.
    """
    value = (app.config.get("DEMO_RESET_TIME") or "").strip()
    if not value or not app.config.get("DEMO_ACCOUNT_ENABLED"):
        return

    reset_at = parse_reset_time(value)
    tz = ZoneInfo(app.config.get("DEMO_RESET_TIMEZONE") or "Europe/London")
    marker_path = os.path.join(app.config["DB_DIR"], RESET_MARKER_FILENAME)

    def _write_marker() -> None:
        with open(marker_path, "w") as marker:
            marker.write(datetime.now(UTC).isoformat())

    def _is_due() -> bool:
        try:
            last_reset = os.path.getmtime(marker_path)
        except FileNotFoundError:
            # First start: count from now, so deploying mid-afternoon does
            # not wipe a demo in progress.
            _write_marker()
            return False
        return last_reset < most_recent_reset(datetime.now(UTC), reset_at, tz).timestamp()

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
                    # tomorrow night rather than on every request.
                    _write_marker()
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
        return None
