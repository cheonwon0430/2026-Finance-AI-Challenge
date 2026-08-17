import pytest
from sqlalchemy import text

from app.infrastructure.database.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_pgvector():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT '[1,2,3]'::vector")
        )

        vector = result.scalar()

        assert vector is not None