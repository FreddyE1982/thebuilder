import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from httpx import AsyncClient, ASGITransport
from rest_api import GymAPI


def test_create_and_list_planned_workouts(tmp_path):
    db_file = tmp_path / "test.db"
    api = GymAPI(db_path=str(db_file))

    async def run_test():
        transport = ASGITransport(app=api.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/planned_workouts", params={"date": "2024-01-01"})
            assert resp.status_code == 200
            pid = resp.json()["id"]
            resp = await client.get("/planned_workouts")
            assert resp.status_code == 200
            ids = [p["id"] for p in resp.json()]
            assert pid in ids

    asyncio.run(run_test())
