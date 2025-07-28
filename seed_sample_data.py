import datetime
from rest_api import GymAPI



def seed() -> None:
    api = GymAPI()
    if api.workouts.fetch_all_workouts():
        print("Database already contains workouts")
        return

    wid = api.workouts.create(datetime.date.today().isoformat(), "strength", "Sample session", "Home", 8)
    ex_id = api.exercises.add(wid, "Bench Press", "Olympic Barbell")
    api.sets.add(ex_id, 5, 100.0, 8)
    api.sets.add(ex_id, 5, 105.0, 9)
    print("Seed data inserted")


if __name__ == "__main__":
    seed()
