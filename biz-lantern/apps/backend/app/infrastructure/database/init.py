from app.infrastructure.database import models
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import engine


async def init_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)