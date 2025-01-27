from sqlmodel import Session, create_engine, select
from src import crud
from src.config.settings import settings
from src.models.user import User, UserCreate
import time


# Retry mechanism for database connection
def create_engine_with_retry(database_uri: str, retries: int = 5, delay: int = 2):
    for i in range(retries):
        try:
            engine = create_engine(database_uri)
            with engine.connect():
                print("Database connection successful!")
                return engine
        except Exception as e:
            print(f"Attempt {i + 1} failed: {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise Exception(
                    "Failed to connect to the database after multiple attempts."
                )


engine = create_engine_with_retry(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            is_verified=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
