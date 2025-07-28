import argparse
import csv
import datetime
import json
import shutil
from typing import Optional

from db import WorkoutRepository, SetRepository
from cli_tools import GitTools
from rest_api import GymAPI


def export_workouts(db_path: str, fmt: str, output_dir: str = ".") -> None:
    workouts = WorkoutRepository(db_path)
    sets = SetRepository(db_path)
    all_w = workouts.fetch_all_workouts()
    for wid, date, *_ in all_w:
        if fmt == "csv":
            data = sets.export_workout_csv(wid)
            out_path = f"{output_dir}/workout_{wid}.csv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(data)
        else:
            data = sets.export_workout_json(wid)
            out_path = f"{output_dir}/workout_{wid}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(data)


def backup_db(db_path: str, backup_path: str) -> None:
    shutil.copy(db_path, backup_path)


def restore_db(backup_path: str, db_path: str) -> None:
    shutil.copy(backup_path, db_path)


def demo_data(db_path: str, yaml_path: str) -> None:
    """Populate the database with demo workouts if empty."""
    api = GymAPI(db_path=db_path, yaml_path=yaml_path)
    if api.workouts.fetch_all_workouts():
        print("Database already contains workouts")
        return
    wid = api.workouts.create(
        datetime.date.today().isoformat(),
        "strength",
        "Demo session",
        "Home",
        8,
    )
    ex_id = api.exercises.add(wid, "Bench Press", "Olympic Barbell")
    api.sets.add(ex_id, 5, 100.0, 8)
    api.sets.add(ex_id, 5, 105.0, 9)
    print("Demo data inserted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Utility commands")
    sub = parser.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export")
    exp.add_argument("--db", default="workout.db")
    exp.add_argument("--fmt", choices=["csv", "json"], default="csv")
    exp.add_argument("--out", default=".")

    bkp = sub.add_parser("backup")
    bkp.add_argument("--db", default="workout.db")
    bkp.add_argument("--out", default="backup.db")

    rst = sub.add_parser("restore")
    rst.add_argument("--in", dest="src", default="backup.db")
    rst.add_argument("--db", default="workout.db")

    demo = sub.add_parser("demo")
    demo.add_argument("--db", default="workout.db")
    demo.add_argument("--yaml", default="settings.yaml")

    args = parser.parse_args()

    if args.cmd == "export":
        export_workouts(args.db, args.fmt, args.out)
    elif args.cmd == "backup":
        backup_db(args.db, args.out)
    elif args.cmd == "restore":
        restore_db(args.src, args.db)
    elif args.cmd == "demo":
        demo_data(args.db, args.yaml)


if __name__ == "__main__":
    main()
