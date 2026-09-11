"""Reset the shared demo account to its seeded demo cases.

    python -m scripts.reset_demo          # report what would be destroyed
    python -m scripts.reset_demo --apply  # destroy it and reseed

Destroys every case the demo account created, and the seeded demo cases
(so edits to them are undone), then seeds the demo cases again. Cases
created by any other account are never touched.

For an automatic reset without cron, set DEMO_RESET_INTERVAL_MINUTES instead.
"""

import argparse
import os

from app import create_app
from app.services.demo_service import (
    find_resettable_cases,
    get_demo_user,
    reset_demo_data,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually reset. Without this the job only reports.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("FLASK_ENV", "development"),
        help="Configuration name to load.",
    )
    args = parser.parse_args(argv)

    app = create_app(args.config)

    with app.app_context():
        demo_user = get_demo_user(app.config)
        if not demo_user:
            print("The demo account is disabled or does not exist. Nothing to do.")
            return 0

        if not args.apply:
            cases = find_resettable_cases(demo_user)
            print(f"Dry run. {len(cases)} case(s) would be destroyed:")
            for case in cases:
                print(f"  - {case.identifier}")
            print("The seeded demo cases would then be recreated.")
            print("Re-run with --apply to carry this out.")
            return 0

        result = reset_demo_data(app.config)
        print(f"Destroyed {len(result.cases_destroyed)} case(s).")
        print(f"Seeded {result.cases_seeded} demo case(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
