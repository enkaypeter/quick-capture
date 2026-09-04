"""Apply the data retention policy.

    python -m scripts.retention          # report what would be destroyed
    python -m scripts.retention --apply  # destroy it

Blocker 11. Archived cases previously stayed on disk forever. This job
permanently erases archived cases past their retention period, and prunes
access logs and login attempts past theirs.

Defaults to a dry run, because the alternative is a scheduled job that
silently destroys casework the first time someone mistimes a cron entry.
Retention periods are configured in config.py and documented in
docs/operations/data-retention.md.
"""

import argparse
import os

from app import create_app
from app.services.access_log_service import AccessLogService
from app.services.login_throttle_service import LoginThrottleService
from app.services.retention_service import RetentionService


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually erase. Without this the job only reports.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("FLASK_ENV", "development"),
        help="Configuration name to load.",
    )
    args = parser.parse_args(argv)

    app = create_app(args.config)

    with app.app_context():
        retention = RetentionService(app.config["UPLOAD_FOLDER"])
        case_days = app.config["RETENTION_ARCHIVED_CASE_DAYS"]
        access_days = app.config["RETENTION_ACCESS_LOG_DAYS"]
        attempt_days = app.config["RETENTION_LOGIN_ATTEMPT_DAYS"]

        expired = retention.find_expired_cases(case_days)

        if not args.apply:
            print(f"Dry run. Retention period for archived cases: {case_days} days.")
            print(f"{len(expired)} case(s) would be permanently erased:")
            for case in expired:
                print(f"  - {case.identifier} (archived {case.archived_at})")
            print(f"Access logs older than {access_days} days would be pruned.")
            print(f"Login attempts older than {attempt_days} days would be pruned.")
            print("Re-run with --apply to carry this out.")
            return 0

        results = retention.purge_expired_cases(case_days)
        for result in results:
            print(
                f"Erased {result.case_identifier}: "
                f"{result.records_deleted} record(s), {result.files_deleted} file(s)"
            )

        access_pruned = AccessLogService.from_config(app.config).prune(access_days)
        attempts_pruned = LoginThrottleService.from_config(app.config).prune(
            attempt_days
        )

        print(f"Erased {len(results)} case(s).")
        print(f"Pruned {access_pruned} access log row(s).")
        print(f"Pruned {attempts_pruned} login attempt row(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
