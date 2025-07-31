import requests
from typing import Optional

class BuilderClient:
    """Simple REST client for the workout API."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def create_workout(self, date: str, **params: str) -> int:
        resp = requests.post(f"{self.base_url}/workouts", params={"date": date, **params})
        resp.raise_for_status()
        return resp.json()["id"]

    def list_workouts(self, **params: str):
        resp = requests.get(f"{self.base_url}/workouts", params=params)
        resp.raise_for_status()
        return resp.json()

    def add_exercise(self, workout_id: int, name: str, equipment: Optional[str] = None) -> int:
        resp = requests.post(
            f"{self.base_url}/workouts/{workout_id}/exercises",
            params={"name": name, "equipment": equipment},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def add_set(self, exercise_id: int, reps: int, weight: float, rpe: int) -> int:
        resp = requests.post(
            f"{self.base_url}/exercises/{exercise_id}/sets",
            params={"reps": reps, "weight": weight, "rpe": rpe},
        )
        resp.raise_for_status()
        return resp.json()["id"]

