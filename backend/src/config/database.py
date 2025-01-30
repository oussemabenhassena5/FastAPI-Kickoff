import time

from sqlmodel import Session, create_engine, select
from src import crud
from src.config.settings import settings
from src.models.user import User, UserCreate


def create_engine_with_retry(database_uri: str, retries: int = 5, delay: int = 2):
    for i in range(retries):
        try:
            print(f"Attempting to connect to database: {database_uri}")
            engine = create_engine(database_uri, echo=True)
            with engine.connect():
                print("Database connection successful!")
                return engine
        except Exception as e:
            print(f"Attempt {i + 1} failed: {e}")
            if i < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise Exception(
                    f"Failed to connect to the database after {retries} attempts. Last error: {str(e)}"
                )


engine = create_engine_with_retry(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    try:
        print("Checking for superuser...")
        user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        if not user:
            print("Superuser not found. Creating superuser...")
            user_in = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
                is_verified=True,
            )
            user = crud.create_user(session=session, user_create=user_in)
            session.commit()  # Make sure to commit the transaction
            print("Superuser created successfully!")
        else:
            print("Superuser already exists!")
    except Exception as e:
        print(f"Error in init_db: {str(e)}")
        session.rollback()
        raise
