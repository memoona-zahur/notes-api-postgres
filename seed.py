"""
Bootstraps the *first* admin (there's no other way to get one — register
always creates role="user"), plus two regular users and a sample category,
for manual/curl testing. Assumes `alembic upgrade head` has already been run
— this script does NOT create tables itself.

Run with: python seed.py
"""
from app.database import SessionLocal
from app import models
from app.auth import hash_password, create_access_token


def get_or_create_user(db, email: str, password: str, role: str) -> models.User:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(email=email, hashed_password=hash_password(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def main() -> None:
    db = SessionLocal()
    try:
        alice = get_or_create_user(db, "alice@example.com", "alice-password", role="user")
        bob = get_or_create_user(db, "bob@example.com", "bob-password", role="user")
        admin = get_or_create_user(db, "admin@example.com", "admin-password", role="admin")

        category = db.query(models.Category).filter(models.Category.name == "General").first()
        if category is None:
            category = models.Category(name="General")
            db.add(category)
            db.commit()
            db.refresh(category)

        if db.query(models.Note).filter(models.Note.owner_id == alice.id).first() is None:
            db.add(models.Note(title="Alice's private note", body="Only Alice should see this.", owner_id=alice.id, category_id=category.id))
        if db.query(models.Note).filter(models.Note.owner_id == bob.id).first() is None:
            db.add(models.Note(title="Bob's private note", body="Only Bob should see this.", owner_id=bob.id))
        db.commit()

        print("Seeded users (password shown is the real login password, for /auth/login testing):")
        print(f"  alice@example.com / alice-password   (role=user,  id={alice.id})")
        print(f"  bob@example.com   / bob-password     (role=user,  id={bob.id})")
        print(f"  admin@example.com / admin-password   (role=admin, id={admin.id})")
        print()
        print("Ready-to-use tokens (skip /auth/login and use these directly with curl):")
        print(f"  ALICE_TOKEN={create_access_token(user_id=alice.id, role=alice.role)}")
        print(f"  BOB_TOKEN={create_access_token(user_id=bob.id, role=bob.role)}")
        print(f"  ADMIN_TOKEN={create_access_token(user_id=admin.id, role=admin.role)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
