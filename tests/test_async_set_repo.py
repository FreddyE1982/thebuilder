import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import AsyncWorkoutRepository, AsyncExerciseRepository, AsyncSetRepository


@pytest.mark.asyncio
async def test_async_set_repository_basic(tmp_path):
    db_file = str(tmp_path / "sets.db")
    workout_repo = AsyncWorkoutRepository(db_file)
    exercise_repo = AsyncExerciseRepository(db_file)
    set_repo = AsyncSetRepository(db_file)

    wid = await workout_repo.create("2024-01-01")
    eid = await exercise_repo.add(wid, "Bench", "Bar")
    sid = await set_repo.add(eid, 5, 100.0, 8)

    detail = await set_repo.fetch_detail(sid)
    assert detail["reps"] == 5

    await set_repo.update(sid, 8, 120.0, 9)
    detail = await set_repo.fetch_detail(sid)
    assert detail["weight"] == 120.0

    await set_repo.set_duration(sid, 60)
    detail = await set_repo.fetch_detail(sid)
    assert detail["start_time"] is not None
    assert detail["end_time"] is not None

    await set_repo.remove(sid)
    rows = await set_repo.fetch_for_exercise(eid)
    assert rows == []
