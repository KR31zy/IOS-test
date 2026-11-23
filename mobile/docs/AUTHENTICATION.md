# Username authentication and password policy

The supplied original FastAPI server accepts **email + password** only. Its account creation, reset and invitation models require a 12-character password. A Flutter UI cannot change these server rules. This folder includes a separate, opt-in source patch for that exact backend; it does not contain an edited copy of the full backend.

## Enable username sign-in

From the new `mobile/` directory with the original `backend/` sibling:

```bash
python3 tools/enable_username_auth.py
# The above performs a dry run, without writing anything.
# Back up the API source AND the database; review the patch.
python3 tools/enable_username_auth.py --apply
cd ../backend
source .venv/bin/activate
# Ensure the existing DATABASE_URL is set, not a new database.
alembic upgrade head
```

On Windows run `python` or `py -3` in place of `python3`. Restart the backend after applying the migration. For a nonstandard backend path specify `--backend /path/to/backend`. The patch requires the supplied migration head `f220261119`, checks source anchors, saves `app/main.py.before_mobile_username` and writes one nullable unique username migration. The patch intentionally does not modify any frontend code. For existing DBs previously created via `create_all` without Alembic history, establish the correct migration baseline with your database administrator; do not blindly stamp the database.

### Behavior

- New mobile registrations choose a unique case-insensitive username (3–32 ASCII letters, digits, periods, underscores or hyphens; starts with a letter or digit). An email is still required for recovery and invitations.
- Sign in with username + password or existing email + password.
- Existing account credentials and IDs remain valid. Sign in once using email, open More → Profile & settings, choose a username. Invitees join through token + password, then choose a username in Profile.
- Minimum new/reset password length is eight characters, not exactly eight. This is the user's requested shorter policy; we recommend longer unique passwords/passphrases (12–15+), especially for sensitive clinical data, and MFA before production. No stored passwords are reset, exposed or generated.
- Web email login stays compatible. Web UI may still require twelve characters for creation/reset until separately updated; server now accepts eight. This patch intentionally changes server-wide password validation, not only mobile. Test all account workflows before rollout.
- Argon2id hashing, same signed cookies, CSRF, membership permissions, existing recovery throttle and session expiration are retained. Username and email attempts for a known account use its canonical email in the existing throttle logic. No authentication bypass or sample users are added.

If you do not want to change the server, do not apply the patch. Build/run with `--dart-define=USERNAME_AUTH=false`; original email and 12-character server rules remain in force. The login screen does not pretend arbitrary usernames are accepted.

## Verification / rollback

Run the supplied `tools/test_username_auth.py` against a disposable SQLite copy of the patched backend, never production. Set an explicit test database URL, migrate it and run from the backend directory with its dependencies installed. Existing web and server tests should also be rerun. In rollback, first stop the app, back up current DB, review the impact (username values would be lost), use Alembic downgrade to `f220261119` while the migration file still exists, then restore the original backend source from version control or the saved copy. Do not delete or reset user accounts. Consult your database administrator for live rollback.
