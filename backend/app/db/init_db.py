from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.database import Base, SessionLocal, engine
from app.db.models import User


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_teacher(db)


def seed_default_teacher(db: Session) -> None:
    existing_user = db.query(User).filter(User.username == settings.DEFAULT_TEACHER_USERNAME).first()
    if existing_user:
        return

    teacher = User(
        username=settings.DEFAULT_TEACHER_USERNAME,
        password_hash=get_password_hash(settings.DEFAULT_TEACHER_PASSWORD),
        role="teacher",
    )
    db.add(teacher)
    db.commit()


if __name__ == "__main__":
    init_database()
    print("Database initialized.")
