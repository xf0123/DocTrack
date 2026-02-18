# DocTrack

Simple document progress tracking web app with login, dashboard, CRUD-style document management, and user setup.

## Features

- Login with username/password.
- Dashboard:
  - Count of on-circulation documents (not yet approved).
  - Count of approved but not yet scanned documents.
  - Duration in days for both groups.
- Documents page:
  - List all documents with filters.
  - Add new documents (type, process, doc no, title; approved/scanned default to No).
  - Approve / scan through modal with date capture and clicked username logging.
- Setup:
  - Admin: add/delete users, change role, change any password.
  - User: change own password only.
- Date display format: `dd-MMM-yyyy`.
- Minimal layout with automatic light/dark theme support.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:4000`

Default admin account:

- Username: `admin`
- Password: `admin123`

## Notes

This app is intended for personal monitoring and is not designed for regulated GMP/21 CFR Part 11 use.
