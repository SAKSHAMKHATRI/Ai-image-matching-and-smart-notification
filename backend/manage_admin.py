#!/usr/bin/env python3
"""Local Admin Role Management Utility for University AI Lost & Found.

Safely grants or revokes the ADMIN role for a specific Firebase user in the local
SQLite database without modifying credentials or affecting other users.

Usage:
  python manage_admin.py --list
  python manage_admin.py --grant <FIREBASE_UID_OR_EMAIL>
  python manage_admin.py --revoke <FIREBASE_UID_OR_EMAIL>
  python manage_admin.py --status <FIREBASE_UID_OR_EMAIL>
  python manage_admin.py --bootstrap [--email admin@chitkara.edu.in] [--password admin1234]
"""

import argparse
import sys
from pathlib import Path

# Ensure backend directory is on python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import db


def list_users() -> None:
    """Print all registered users, their profile names/emails, and their current roles."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id AS user_id,
                u.firebase_uid,
                u.role,
                u.status,
                p.full_name,
                p.university_email,
                p.campus
            FROM users u
            LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
            ORDER BY u.id ASC
            """
        ).fetchall()

    if not rows:
        print("No users found in database.")
        return

    print("=" * 80)
    print(f"{'ID':<5} {'Role':<10} {'Status':<10} {'Name':<22} {'Email / UID'}")
    print("=" * 80)
    for r in rows:
        email_or_uid = r["university_email"] or r["firebase_uid"]
        name = r["full_name"] or "(No profile created)"
        role_marker = f"[{r['role']}]" if r["role"] == "ADMIN" else r["role"]
        print(f"{r['user_id']:<5} {role_marker:<10} {r['status']:<10} {name:<22} {email_or_uid}")
        if r["university_email"]:
            print(f"      UID: {r['firebase_uid']}")
    print("=" * 80)


def resolve_firebase_uid(identifier: str) -> str:
    """Resolve a given identifier (email or Firebase UID) to a firebase_uid."""
    cleaned = identifier.strip()
    # Check if identifier matches a profile email
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT firebase_uid FROM student_profiles WHERE LOWER(university_email) = LOWER(?)",
            (cleaned,),
        ).fetchone()
        if row:
            return str(row[0])

        # Check if identifier matches an existing users.firebase_uid
        user_row = conn.execute(
            "SELECT firebase_uid FROM users WHERE firebase_uid = ?",
            (cleaned,),
        ).fetchone()
        if user_row:
            return str(user_row[0])

    # If not found yet, treat identifier directly as the Firebase UID
    return cleaned


def set_user_role(identifier: str, role: str) -> None:
    """Assign role ('ADMIN', 'STUDENT', 'STAFF') to the specified user."""
    firebase_uid = resolve_firebase_uid(identifier)
    user_id = db.ensure_user(firebase_uid)

    with db.get_connection() as conn:
        conn.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (role, user_id),
        )
        updated_user = conn.execute(
            """
            SELECT u.id, u.firebase_uid, u.role, u.status, p.full_name, p.university_email
            FROM users u
            LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()

    if updated_user:
        name = updated_user["full_name"] or "(No profile created yet)"
        email = updated_user["university_email"] or "(No email in profile)"
        print(f"[+] Success: User role updated to [{role}]")
        print(f"  User ID      : {updated_user['id']}")
        print(f"  Firebase UID : {updated_user['firebase_uid']}")
        print(f"  Name         : {name}")
        print(f"  Email        : {email}")
        print(f"  Role         : {updated_user['role']}")
        print(f"  Status       : {updated_user['status']}")
    else:
        print(f"[-] Failed to update user with identifier: {identifier}")


def show_user_status(identifier: str) -> None:
    """Display the current role and profile details for a user."""
    firebase_uid = resolve_firebase_uid(identifier)
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.firebase_uid, u.role, u.status, p.full_name, p.university_email, p.campus
            FROM users u
            LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
            WHERE u.firebase_uid = ?
            """,
            (firebase_uid,),
        ).fetchone()

    if not row:
        print(f"No user record found for identifier: {identifier}")
        return

    print("=" * 60)
    print("User Account Status:")
    print(f"  Database ID  : {row['id']}")
    print(f"  Firebase UID : {row['firebase_uid']}")
    print(f"  Name         : {row['full_name'] or '(No profile)'}")
    print(f"  Email        : {row['university_email'] or '(No profile)'}")
    print(f"  Campus       : {row['campus'] or '(No profile)'}")
    print(f"  Role         : {row['role']}")
    print(f"  Status       : {row['status']}")
    print("=" * 60)


def bootstrap_admin(
    email: str = "admin@chitkara.edu.in",
    password: str = "admin1234",
) -> None:
    """Safely create or update a dedicated Firebase admin account and assign role=ADMIN in SQLite."""
    print("=" * 60)
    print(f"Bootstrapping Admin Account: {email}")
    print("=" * 60)

    # 1. Firebase Auth provision
    firebase_uid = None
    try:
        from app.auth.firebase import get_firebase_app
        from firebase_admin import auth

        fb_app = get_firebase_app()
        try:
            fb_user = auth.get_user_by_email(email, app=fb_app)
            firebase_uid = fb_user.uid
            print(f"[+] Found existing Firebase Auth account (UID: {firebase_uid})")
            if password:
                auth.update_user(firebase_uid, password=password, app=fb_app)
                print("[+] Updated Firebase Auth password")
        except auth.UserNotFoundError:
            fb_user = auth.create_user(
                email=email,
                password=password,
                email_verified=True,
                app=fb_app,
            )
            firebase_uid = fb_user.uid
            print(f"[+] Created new Firebase Auth account (UID: {firebase_uid})")
    except Exception as exc:
        print(f"[!] Note: Firebase Admin provisioning skipped/failed ({exc}).")
        # If Firebase is offline/not configured, resolve UID from local DB if already present
        firebase_uid = resolve_firebase_uid(email)
        if firebase_uid == email:
            # Fallback deterministic dev UID
            firebase_uid = "admin-chitkara-uid-001"
            print(f"[+] Using local fallback Firebase UID: {firebase_uid}")

    # 2. SQLite Database provision
    user_id = db.ensure_user(firebase_uid, role="ADMIN")
    db.update_user_role(user_id, "ADMIN")
    print(f"[+] Set users.role = 'ADMIN' for user ID: {user_id}")

    print("=" * 60)
    print("Admin Account Ready for Login:")
    print(f"  Email        : {email}")
    print(f"  Password     : {password}")
    print(f"  Firebase UID : {firebase_uid}")
    print(f"  Role         : ADMIN")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local Admin Role Management Utility",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        action="store_true",
        help="List all users and their current roles in the local database",
    )
    group.add_argument(
        "--grant",
        metavar="IDENTIFIER",
        help="Grant ADMIN role to a user (specify Firebase UID or university email)",
    )
    group.add_argument(
        "--revoke",
        metavar="IDENTIFIER",
        help="Revoke ADMIN role and revert user to STUDENT",
    )
    group.add_argument(
        "--status",
        metavar="IDENTIFIER",
        help="Check role and profile status of a user",
    )
    group.add_argument(
        "--bootstrap",
        action="store_true",
        help="Bootstrap or update dedicated Firebase admin account and SQLite role",
    )
    parser.add_argument(
        "--email",
        default="admin@chitkara.edu.in",
        help="Admin email address for bootstrap (default: admin@chitkara.edu.in)",
    )
    parser.add_argument(
        "--password",
        default="admin1234",
        help="Admin password for bootstrap (default: admin1234)",
    )

    args = parser.parse_args()

    db.initialize_database()

    if args.list:
        list_users()
    elif args.grant:
        set_user_role(args.grant, "ADMIN")
    elif args.revoke:
        set_user_role(args.revoke, "STUDENT")
    elif args.status:
        show_user_status(args.status)
    elif args.bootstrap:
        bootstrap_admin(email=args.email, password=args.password)


if __name__ == "__main__":
    main()
