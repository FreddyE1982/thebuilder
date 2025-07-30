import argparse
import csv
import datetime
import json
import shutil
import subprocess
from typing import Optional

from db import WorkoutRepository, SetRepository
from tools import WeightConverter
from cli_tools import GitTools
from rest_api import GymAPI
import requests
import time


def export_workouts(db_path: str, fmt: str, output_dir: str = ".") -> None:
    workouts = WorkoutRepository(db_path)
    sets = SetRepository(db_path)
    all_w = workouts.fetch_all_workouts()
    for wid, date, *_ in all_w:
        if fmt == "csv":
            data = sets.export_workout_csv(wid)
            out_path = f"{output_dir}/workout_{wid}.csv"
        elif fmt == "json":
            data = sets.export_workout_json(wid)
            out_path = f"{output_dir}/workout_{wid}.json"
        else:
            data = sets.export_workout_xml(wid)
            out_path = f"{output_dir}/workout_{wid}.xml"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(data)


def backup_db(db_path: str, backup_path: str) -> None:
    shutil.copy(db_path, backup_path)


def restore_db(backup_path: str, db_path: str) -> None:
    shutil.copy(backup_path, db_path)


def import_strava(csv_path: str, db_path: str) -> None:
    """Import workouts from a Strava CSV export."""
    api = GymAPI(db_path=db_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("Activity Date") or row.get("Date")
            if not date:
                continue
            wtype = row.get("Activity Type") or row.get("Sport", "Cardio")
            distance = float(row.get("Distance", 0.0))
            wid = api.workouts.create(date, wtype)
            ex_id = api.exercises.add(wid, wtype, "Bodyweight")
            api.sets.add(ex_id, 1, distance, 0)


def benchmark(url: str, runs: int = 10) -> None:
    times: list[float] = []
    for _ in range(runs):
        t0 = time.time()
        requests.get(f"{url}/health", timeout=5)
        times.append(time.time() - t0)
    avg = sum(times) / len(times)
    print(f"Average /health response time over {runs} runs: {avg:.4f}s")


def security_audit() -> None:
    result = subprocess.run(["pip-audit"], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
    else:
        print(result.stdout)


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
    exp.add_argument("--fmt", choices=["csv", "json", "xml"], default="csv")
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

    bench = sub.add_parser("benchmark")
    bench.add_argument("--url", default="http://localhost:8000")
    bench.add_argument("--runs", type=int, default=10)

    audit = sub.add_parser("audit")

    imp = sub.add_parser("import_strava")
    imp.add_argument("--csv", required=True)
    imp.add_argument("--db", default="workout.db")

    conv = sub.add_parser("convert")
    conv.add_argument("--weight", type=float, required=True)
    conv.add_argument("--unit", choices=["kg", "lb"], required=True)

    args = parser.parse_args()

    if args.cmd == "export":
        export_workouts(args.db, args.fmt, args.out)
    elif args.cmd == "backup":
        backup_db(args.db, args.out)
    elif args.cmd == "restore":
        restore_db(args.src, args.db)
    elif args.cmd == "demo":
        demo_data(args.db, args.yaml)
    elif args.cmd == "benchmark":
        benchmark(args.url, args.runs)
    elif args.cmd == "audit":
        security_audit()
    elif args.cmd == "import_strava":
        import_strava(args.csv, args.db)
    elif args.cmd == "convert":
        if args.unit == "kg":
            print(f"{args.weight} kg = {WeightConverter.kg_to_lb(args.weight)} lb")
        else:
            print(f"{args.weight} lb = {WeightConverter.lb_to_kg(args.weight)} kg")


if __name__ == "__main__":
    main()
