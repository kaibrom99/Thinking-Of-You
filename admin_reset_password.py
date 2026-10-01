"""Reset someone's password (there is no email reset yet).

Usage:  python admin_reset_password.py their@email.com NewPassword123
To reset an account on the live server, set DATABASE_URL to your Neon address first.
"""
import secrets
import sys

from sqlmodel import Session, select

import main

if len(sys.argv) != 3 or len(sys.argv[2]) < 8:
    sys.exit("Usage: python admin_reset_password.py email new_password (at least 8 characters)")
email, new_pw = sys.argv[1].strip().lower(), sys.argv[2]
with Session(main.engine) as s:
    user = s.exec(select(main.User).where(main.User.email == email)).first()
    if not user:
        sys.exit("No account with that email.")
    user.salt = secrets.token_hex(16)
    user.pw_hash = main.hash_pw(new_pw, user.salt)
    for row in s.exec(select(main.LoginToken).where(main.LoginToken.user_id == user.id)).all():
        s.delete(row)  # logs them out everywhere
    s.add(user)
    s.commit()
print("Done. Give them the new password and ask them to keep it private.")