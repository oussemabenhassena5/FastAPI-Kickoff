import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from src.config import settings
from src.models.user import User, UserCreate
from src.routes import crud
from tenacity import (
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Configure async engine with connection pool settings
engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=settings.DB_ECHO_LOG,  # Control via environment variable
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Check connections before use
)

# Use async session factory with scoped sessions
AsyncSessionFactory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions with automatic cleanup"""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rollback due to error: {str(e)}")
            raise
        finally:
            await session.close()


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(exc.OperationalError),
    before=before_log(logger, logging.INFO),
)
async def init_db() -> None:
    """Initialize database with connection retries and schema validation"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database schema validated successfully")
    except Exception as e:
        logger.critical(f"Database initialization failed: {str(e)}")
        raise


async def create_superuser() -> None:
    """Idempotent superuser creation with proper error handling"""
    async with get_db_session() as session:
        try:
            existing_user = await session.exec(
                select(User).where(User.email == settings.FIRST_SUPERUSER)
            ).first()

            if existing_user:
                logger.info("Superuser already exists")
                return

            superuser = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
                is_verified=True,
            )

            await crud.create_user(session=session, user_create=superuser)
            await session.commit()
            logger.info("Superuser created successfully")

        except Exception as e:
            logger.error(f"Superuser creation failed: {str(e)}")
            await session.rollback()
            raise
