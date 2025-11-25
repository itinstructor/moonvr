import os
import sys
from getpass import getpass
from werkzeug.security import generate_password_hash
from blog.models import User
from database import db

# --- Flask app context setup ---
from main_app import app

DEFAULT_PASSWORD = os.environ.get("DEFAULT_RESET_PASSWORD", "")

if __name__ == "__main__":
    print(f"This will reset ALL user passwords to: {DEFAULT_PASSWORD}")
    confirm = input("Type YES to continue: ")
    if confirm.strip().upper() != "YES":
        print("Aborted.")
        sys.exit(1)

    with app.app_context():
        users = User.query.all()
        if not users:
            print("No users found.")
            sys.exit(0)
        for user in users:
            user.password_hash = generate_password_hash(DEFAULT_PASSWORD)
            print(f"Reset password for user: {user.username}")
        db.session.commit()
        print(f"All user passwords have been reset to: {DEFAULT_PASSWORD}")
