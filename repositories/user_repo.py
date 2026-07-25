"""User repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models.user import User


class UserRepository:

    @staticmethod
    def create(
        db: Session,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
    ) -> User:
        user = User(email=email, hashed_password=hashed_password, full_name=full_name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def update(db: Session, user: User, **fields) -> User:
        for key, value in fields.items():
            if hasattr(user, key):
                setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        db.delete(user)
        db.commit()
