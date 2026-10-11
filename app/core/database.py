from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator
from app.core.config import get_settings

settings = get_settings()

from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.database_url_async,
    echo=settings.DEBUG,
    poolclass=NullPool,
)


async def create_db_and_tables():
    """Create all tables in the database. Used for the prototype."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

