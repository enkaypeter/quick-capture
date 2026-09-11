# ADR-009: Shared Demo Account

## Status

Accepted — for demo deployments only, never alongside live data

## Date

2026-09-11

## Context

The MVP is shown to people by giving them one demo login. That clashes with two
controls from [ADR-008](008-security-controls-for-production.md):

- **Mandatory MFA for admins.** The demo account is an admin, so it must enrol
  in TOTP. Only one phone can hold the secret, so nobody else can log in.
- **Everything is kept.** Each person who tries the app leaves cases, notes and
  files behind. The next person sees a mess instead of the demo cases.

## Decision

**Any 6-digit code for the demo account.** With `DEMO_ACCOUNT_SHARED_MFA=true`,
the demo account is seeded already enrolled, so it is never sent to
`/mfa/setup`, and its code prompt accepts any 6 digits. The code prompt is kept
rather than skipped, so a demo still shows the real login flow. Every other
account still needs a real code.

**A nightly reset.** With `DEMO_RESET_TIME` set (for example `03:00`, in
`DEMO_RESET_TIMEZONE`), the first request after that time destroys every case
the demo account created, destroys the seeded demo cases, and seeds them again.
`python -m scripts.reset_demo --apply` does the same on demand.

- It runs lazily on a request rather than from a scheduler, so the demo host
  needs no cron entry. A marker file beside the database records the last reset
  so every gunicorn worker agrees, and a file lock stops two workers resetting
  at once.
- The first start only writes the marker, so deploying during the day does not
  wipe a demo in progress.
- Cases created by any other account are never touched.
- The reset writes no erasure log rows. The data is fictional, and a row per
  case per night would bury the real erasures the log exists to prove.

## Consequences

- An admin account is protected by a shared password alone. The production
  configuration guard therefore refuses `DEMO_ACCOUNT_SHARED_MFA` unless
  `ALLOW_DEMO_IN_PRODUCTION=true`, the existing opt-in for demo deployments.
- Anyone using the demo late at night can lose their work at the reset time.
- All demo users share one account lockout: 5 wrong passwords from anyone locks
  everyone out for 15 minutes.
- The reset does not remove invite codes created by the demo account, or
  accounts registered with them. Notes and interactions the demo account adds
  to other accounts' cases also stay.

## Alternatives Considered

**Reject every write from the demo account.** Nothing to clean up, but people
could not create a case, which is most of what a demo shows.

**Skip MFA entirely for the demo account.** Simpler, but the demo would no
longer show the login flow real admins go through.

**Reset on a fixed interval.** Easy to reason about, but an hourly reset lands
in the middle of someone's demo. A nightly reset lands when nobody is using it.

**A cron job running `scripts/reset_demo.py`.** Works, and the script supports
it, but needs access to the host's scheduler. The in-app reset needs nothing
beyond the environment variable.
