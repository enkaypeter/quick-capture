# Admin Guide

Use this guide to manage access and view reports.

> **Do not put real people's details in this app yet.**
>
> Four things still have to happen first, and none of them are software work:
>
> 1. A data protection impact assessment must be completed.
> 2. The charity must agree how long records are kept.
> 3. The trustees must sign off that every worker can read every case.
> 4. Someone must restore a backup and prove it works.
>
> Until then, use the demo cases only. See
> [the go-live checklist](../operations/go-live-checklist.md).

## Log In As Admin

1. Open the app.
2. Select `Login`.
3. Enter your admin email address.
4. Enter your password.
5. Select `Login`.
6. Enter the 6-digit code from your authenticator app.

For local demo use:

- Email: `demo@quickcapture.local`
- Password: `demo-password-123`
- Code: any 6 digits, for example `123456`

The demo account is shared, so its code prompt accepts any 6 digits. Your own
admin account needs the real code from your authenticator app.

## Set Up Two-Factor Authentication

Admin accounts must use two-factor authentication. The app will ask you to set
it up the first time you log in, before you can do anything else.

You need an authenticator app on your phone. Microsoft Authenticator, Google
Authenticator and 1Password all work.

1. Log in with your email and password.
2. The app shows a square QR code.
3. Open your authenticator app and scan the code.

If you cannot scan it, type the key shown underneath into your app by hand.

4. Your app now shows a 6-digit code that changes every 30 seconds.
5. Type that code into the app.
6. Select `Turn on two-factor authentication`.

## Save Your Recovery Codes

After setup, the app shows eight recovery codes.

**These are shown once. You cannot get them back.**

1. Print them, or write them down.
2. Keep them somewhere separate from your phone.

Each code works one time. Use one to log in if you lose your phone.

If you lose both your phone and your codes, nobody can let you back in. The
account has to be reset directly in the database.

To issue new codes, select `Security`, then
`Issue new recovery codes`. Your old codes stop working straight away.

## Unlock A Locked Account

The app locks an account after 5 wrong passwords. The lock clears itself after
15 minutes, or you can clear it now.

1. Select `Accounts`.
2. Find the person. Locked accounts show `Locked`.
3. Select `Unlock`.

Tell the person their password has not changed. They can try again.

## See Who Has An Account

Select `Accounts`.

The page shows, for every account:

- email address
- name
- role
- whether two-factor authentication is on
- whether the account is locked

Every account on this list can read every active case, including risk notes and
mental health notes.

## Create An Invite Code

Use invite codes when a new user needs an account.

1. Log in as admin.
2. Select `Invite Codes`.
3. Type a label.

The label can be the person's name or the reason for the code.

4. Set `Uses`.

Use `1` for one person.

5. Select `Create`.
6. Copy the new code.
7. Send the code through the agreed safe channel.

The app does not email the code for you.

## Deny An Invite Code

Deny a code if it should no longer work.

1. Select `Invite Codes`.
2. Find the code.
3. Select `Deny`.

A denied code cannot be used to sign up.

## Check Invite Code Status

Open `Invite Codes`.

The page shows:

- the code
- the label
- the status
- how many times it has been used
- who used it
- when it was made

Status meanings:

- `Active`: the code can still be used.
- `Used`: the code has reached its use limit.
- `Denied`: the code has been blocked.

## Help A User Sign Up

1. Create an invite code.
2. Send the code to the user.
3. Ask the user to open `Sign Up`.
4. Ask them to enter their email, first name, invite code and password.
5. Ask them to select `Sign Up`.

The user is logged in after sign-up.

## See Who Has Read A Case

The app records who opens a case, downloads a document, reads the activity
history or exports the report file.

This is separate from the activity list, which shows who *changed* a case.

Any user can see the reading history for a case. It is at
`/cases/<case number>/access-log`.

## Permanently Erase A Case

`Delete` archives a case. It hides it from the active list but keeps the record,
which is what you want if someone deletes a case by mistake.

Permanent erasure is different. It destroys the case, its notes, its documents,
its voice recordings and its history. There is no undo and no way to get it
back.

Use it when:

- someone asks you to erase their data and the charity agrees to do so, or
- a record was created in error.

Before you erase, check with the charity's data protection lead. Safeguarding
records are sometimes kept even when someone asks for erasure. That decision is
not yours to make alone.

To erase:

1. Open the case.
2. Choose permanent erasure.
3. Type the case number exactly as shown to confirm.

The app records what was erased, when, and who asked for it, at `Erasure log`.
That record holds the case number and counts only. It does not keep any of the
erased information.

Note that backups made before the erasure still hold the record. Those age out
as backups rotate. Tell the person this if they ask.

## Old Cases Are Erased Automatically

Archived cases are permanently erased once they pass the charity's retention
period. This runs as a scheduled job.

Active cases are never erased by this job, however old they are.

The retention period is set by the charity. Check
`docs/operations/data-retention.md` for the current value.

## View Reports

1. Select `Reports`.
2. Read the case and interaction counts.
3. Use the quick tag counts to see common support work.
4. Select `Export CSV` if you need a spreadsheet file.

The report uses active cases and interaction tags.

## Review Demo Cases

Local installs include 10 fictional demo cases.

Use them to test:

- search
- case status
- risk ratings
- quick interactions
- follow-ups
- documents
- reports

These are not real people.

## Reset Demo Data

Anything created while logged in as the demo account can be cleared, putting
the 10 demo cases back as they started. Edits to the demo cases are undone too.
Cases created by other accounts are not touched.

To reset now:

```bash
.venv/bin/python -m scripts.reset_demo          # shows what would be deleted
.venv/bin/python -m scripts.reset_demo --apply  # deletes it and reseeds
```

A demo deployment can reset every night instead. Set `DEMO_RESET_TIME` to a
time nobody uses it, such as `03:00`. Anything created in the demo account
before that time is gone the next morning.

## Turn Off Demo Cases

For an empty local case list, start the app with:

```bash
DEMO_CASES_ENABLED=false .venv/bin/python main.py
```

For production, keep demo data off:

```bash
DEMO_ACCOUNT_ENABLED=false
DEMO_CASES_ENABLED=false
BOOTSTRAP_INVITE_ENABLED=false
```

## What Admins Cannot Do Yet

Admins cannot yet:

- change user roles in the app
- disable or remove user accounts in the app
- reset a user's password in the app
- change quick tags in the app
- change report fields in the app

These need someone with database access. They remain outstanding.
