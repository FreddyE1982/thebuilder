import os
import sys
import asyncio
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import AsyncBaseRepository, AsyncWorkoutRepository

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


@pytest.mark.asyncio
async def test_async_workout_repo(tmp_path):
    db_file = str(tmp_path / "workout.db")
    repo = AsyncWorkoutRepository(db_file)
    wid = await repo.create("2024-01-01")
    assert wid == 1
    rows = await repo.fetch_all_workouts()
    assert rows[0][0] == 1
    await repo.delete(wid)
    assert await repo.fetch_all_workouts() == []
