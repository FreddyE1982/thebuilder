import os
import sys
import asyncio
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (
    AsyncBaseRepository,
    AsyncWorkoutRepository,
    AsyncTagRepository,
    AsyncExerciseRepository,
    AsyncReactionRepository,
    AsyncBodyWeightRepository,
    AsyncNotificationRepository,
)

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


@pytest.mark.asyncio
async def test_async_tag_repo(tmp_path):
    db_file = str(tmp_path / "tags.db")
    repo = AsyncTagRepository(db_file)
    tid = await repo.add("test")
    assert tid == 1
    rows = await repo.fetch_all()
    assert rows == [(1, "test")]


@pytest.mark.asyncio
async def test_async_exercise_repo(tmp_path):
    db_file = str(tmp_path / "exercises.db")
    workout_repo = AsyncWorkoutRepository(db_file)
    ex_repo = AsyncExerciseRepository(db_file)
    wid = await workout_repo.create("2024-01-02")
    ex_id = await ex_repo.add(wid, "Bench", "Bar")
    rows = await ex_repo.fetch_for_workout(wid)
    assert rows[0][1] == "Bench"
    await ex_repo.update_name(ex_id, "Bench Press")
    detail = await ex_repo.fetch_detail(ex_id)
    assert detail[1] == "Bench Press"
    await ex_repo.remove(ex_id)
    assert await ex_repo.fetch_for_workout(wid) == []


@pytest.mark.asyncio
async def test_async_reaction_repo(tmp_path):
    db_file = str(tmp_path / "react.db")
    workout_repo = AsyncWorkoutRepository(db_file)
    wid = await workout_repo.create("2024-01-03")
    repo = AsyncReactionRepository(db_file)
    await repo.react(wid, "👍")
    rows = await repo.list_for_workout(wid)
    assert rows == [("👍", 1)]


@pytest.mark.asyncio
async def test_async_body_weight_repo(tmp_path):
    db_file = str(tmp_path / "bw.db")
    repo = AsyncBodyWeightRepository(db_file)
    eid = await repo.log("2024-01-01", 80.5)
    rows = await repo.fetch_history()
    assert rows == [(eid, "2024-01-01", 80.5)]
    await repo.update(eid, "2024-01-02", 82.0)
    rows = await repo.fetch_history("2024-01-02", "2024-01-02")
    assert rows[0][2] == 82.0
    assert rows[0][1] == "2024-01-02"
    await repo.delete(eid)
    assert await repo.fetch_history() == []


@pytest.mark.asyncio
async def test_async_notification_repo(tmp_path):
    db_file = str(tmp_path / "notif.db")
    repo = AsyncNotificationRepository(db_file)
    nid = await repo.add("hello")
    notes = await repo.fetch_all()
    assert notes[0]["id"] == nid
    assert notes[0]["message"] == "hello"
    assert notes[0]["read"] is False
    await repo.mark_read(nid)
    notes = await repo.fetch_all()
    assert notes[0]["read"] is True
    count = await repo.unread_count()
    assert count == 0

