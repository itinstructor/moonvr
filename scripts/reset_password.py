import os
import sys
from getpass import getpass
from werkzeug.security import generate_password_hash

# Ensure project root is on sys.path so `blog` and `database` can be imported
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blog.models import User
from database import db

# --- Flask app context setup ---
from main_app import app


MIN_PASSWORD_LENGTH = 12


def validate_password(pw: str):
    if len(pw) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    complexity = 0
    if any(c.isupper() for c in pw):
        complexity += 1
    if any(c.islower() for c in pw):
        complexity += 1
    if any(c.isdigit() for c in pw):
        complexity += 1
    if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in pw):
        complexity += 1
    if complexity < 3:
        return False, 'Password must contain at least 3 of: uppercase, lowercase, number, symbol.'
    return True, ''


def choose_user(users):
    print('\nAvailable users:')
    for i, u in enumerate(users, start=1):
        flags = []
        if getattr(u, 'is_admin', False):
            flags.append('admin')
        if getattr(u, 'is_active', True) is False:
            flags.append('inactive')
        flagstr = f" ({', '.join(flags)})" if flags else ''
        print(f"  {i}. {u.username}{flagstr}")
    print('')
    sel = input("Enter user number or username (or 'q' to quit): ").strip()
    if sel.lower() == 'q' or sel == '':
        return None
    # try number
    try:
        idx = int(sel)
        if 1 <= idx <= len(users):
            return users[idx - 1]
        else:
            print('Invalid selection number.')
            return None
    except ValueError:
        # treat as username
        for u in users:
            if u.username == sel:
                return u
        print('No user with that username found.')
        return None


if __name__ == "__main__":
    with app.app_context():
        users = User.query.order_by(User.username).all()
        if not users:
            print("No users found.")
            sys.exit(0)

        user = None
        while not user:
            user = choose_user(users)
            if user is None:
                print('No user selected, exiting.')
                sys.exit(0)

        print(f"Resetting password for: {user.username}")
        # prompt for password twice
        while True:
            pw = getpass('New password: ')
            pw2 = getpass('Confirm password: ')
            if pw != pw2:
                print('Passwords do not match — try again.')
                continue
            ok, msg = validate_password(pw)
            if not ok:
                print(f'Invalid password: {msg}')
                retry = input('Try again? (y/N): ').strip().lower()
                if retry == 'y':
                    continue
                else:
                    print('Aborted.')
                    sys.exit(1)
            # valid
            break

        user.password_hash = generate_password_hash(pw)
        try:
            db.session.commit()
            print(f'Password reset for user {user.username}.')
        except Exception as e:
            db.session.rollback()
            print(f'Failed to update password: {e}')
            sys.exit(1)
