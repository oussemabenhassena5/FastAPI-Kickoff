from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, SQLModel

from .config.database import engine, init_db
from .config.settings import settings
from .routes import auth, me, user

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"/{settings.API_STR}/openapi.json",
)


def create_db_and_tables():
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("Database tables created successfully!")


@app.on_event("startup")
async def startup():
    # Create tables first
    create_db_and_tables()

    # Then initialize the database with superuser
    with Session(engine) as session:
        init_db(session)


# Rest of your code remains the same...
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["Auth"], prefix="/api/auth")
app.include_router(me.router, tags=["Me"], prefix="/api/me")
app.include_router(user.router, tags=["Users"], prefix="/api/users")
