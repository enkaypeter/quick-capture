# Admin Guide

Use this guide to manage access and view reports.

## Log In As Admin

1. Open the app.
2. Select `Login`.
3. Enter your admin email address.
4. Enter your password.
5. Select `Login`.

For local demo use:

- Email: `demo@quickcapture.local`
- Password: `demo-password-123`

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

The MVP does not yet have a full user admin page.

Admins cannot yet:

- change user roles in the app
- disable user accounts in the app
- reset passwords in the app
- change quick tags in the app
- change report fields in the app

These tasks remain outstanding.
