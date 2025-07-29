import os
import sys
import asyncio
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import AsyncBaseRepository

class NumberRepository(AsyncBaseRepository):
    async def init_db(self) -> None:
        async with self._async_connection() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS numbers (val INTEGER)")
            await conn.commit()

    async def add(self, val: int) -> int:
        return await self.execute("INSERT INTO numbers (val) VALUES (?)", (val,))

    async def all(self):
        rows = await self.fetch_all("SELECT val FROM numbers")
        return [r[0] for r in rows]

@pytest.mark.asyncio
async def test_async_repository(tmp_path):
    repo = NumberRepository(str(tmp_path / "test.db"))
    await repo.init_db()
    await repo.add(5)
    assert await repo.all() == [5]
