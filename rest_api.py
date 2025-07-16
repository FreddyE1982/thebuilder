import datetime
from fastapi import FastAPI, HTTPException, Response
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    EquipmentRepository,
    ExerciseCatalogRepository,
    MuscleRepository,
    ExerciseNameRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
    GamificationRepository,
)
from planner_service import PlannerService
from recommendation_service import RecommendationService
from stats_service import StatisticsService
from gamification_service import GamificationService
from tools import ExercisePrescription


class GymAPI:
    """Provides REST endpoints for workout logging."""

    def __init__(self, db_path: str = "workout.db") -> None:
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.planned_workouts = PlannedWorkoutRepository(db_path)
        self.planned_exercises = PlannedExerciseRepository(db_path)
        self.planned_sets = PlannedSetRepository(db_path)
        self.equipment = EquipmentRepository(db_path)
        self.exercise_catalog = ExerciseCatalogRepository(db_path)
        self.muscles = MuscleRepository(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)
        self.settings = SettingsRepository(db_path)
        self.pyramid_tests = PyramidTestRepository(db_path)
        self.pyramid_entries = PyramidEntryRepository(db_path)
        self.game_repo = GamificationRepository(db_path)
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings,
        )
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
            self.gamification,
        )
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names,
            self.settings,
            self.gamification,
        )
        self.statistics = StatisticsService(
            self.sets,
            self.exercise_names,
            self.settings,
        )
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/equipment/types")
        def list_equipment_types():
            return self.equipment.fetch_types()

        @self.app.get("/equipment")
        def list_equipment(
            equipment_type: str = None,
            prefix: str = None,
            muscles: str = None,
        ):
            muscs = muscles.split("|") if muscles else None
            return self.equipment.fetch_names(equipment_type, prefix, muscs)

        @self.app.get("/equipment/{name}")
        def get_equipment(name: str):
            muscles = self.equipment.fetch_muscles(name)
            rows = self.equipment.fetch_all(
                "SELECT equipment_type FROM equipment WHERE name = ?;", (name,)
            )
            eq_type = rows[0][0] if rows else None
            return {"name": name, "type": eq_type, "muscles": muscles}

        @self.app.post("/equipment")
        def add_equipment(equipment_type: str, name: str, muscles: str):
            try:
                eid = self.equipment.add(
                    equipment_type, name, muscles.split("|")
                )
                return {"id": eid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/muscles")
        def list_muscles():
            return self.muscles.fetch_all()

        @self.app.post("/muscles/link")
        def link_muscles(name1: str, name2: str):
            self.muscles.link(name1, name2)
            return {"status": "linked"}

        @self.app.post("/muscles/alias")
        def add_alias(new_name: str, existing: str):
            self.muscles.add_alias(new_name, existing)
            return {"status": "added"}

        @self.app.get("/exercise_names")
        def list_exercise_names():
            return self.exercise_names.fetch_all()

        @self.app.post("/exercise_names/link")
        def link_exercise_names(name1: str, name2: str):
            self.exercise_names.link(name1, name2)
            return {"status": "linked"}

        @self.app.post("/exercise_names/alias")
        def add_exercise_alias(new_name: str, existing: str):
            self.exercise_names.add_alias(new_name, existing)
            return {"status": "added"}

        @self.app.get("/exercise_catalog/muscle_groups")
        def list_muscle_groups():
            return self.exercise_catalog.fetch_muscle_groups()

        @self.app.get("/exercise_catalog")
        def list_exercise_catalog(
            muscle_groups: str = None,
            muscles: str = None,
            equipment: str = None,
            prefix: str = None,
        ):
            groups = muscle_groups.split("|") if muscle_groups else None
            muscs = muscles.split("|") if muscles else None
            return self.exercise_catalog.fetch_names(
                groups,
                muscs,
                equipment,
                prefix,
            )

        @self.app.get("/exercise_catalog/{name}")
        def get_exercise_detail(name: str):
            data = self.exercise_catalog.fetch_detail(name)
            if not data:
                raise HTTPException(status_code=404, detail="not found")
            (
                muscle_group,
                variants,
                equipment_names,
                primary_muscle,
                secondary_muscle,
                tertiary_muscle,
                other_muscles,
                _,
            ) = data
            return {
                "muscle_group": muscle_group,
                "variants": variants.split("|") if variants else [],
                "equipment_names": equipment_names.split("|") if equipment_names else [],
                "primary_muscle": primary_muscle,
                "secondary_muscle": secondary_muscle.split("|") if secondary_muscle else [],
                "tertiary_muscle": tertiary_muscle.split("|") if tertiary_muscle else [],
                "other_muscles": other_muscles.split("|") if other_muscles else [],
            }

        @self.app.post("/exercise_catalog")
        def add_exercise_catalog(
            muscle_group: str,
            name: str,
            variants: str,
            equipment_names: str,
            primary_muscle: str,
            secondary_muscle: str = "",
            tertiary_muscle: str = "",
            other_muscles: str = "",
        ):
            try:
                eid = self.exercise_catalog.add(
                    muscle_group,
                    name,
                    variants,
                    equipment_names,
                    primary_muscle,
                    secondary_muscle,
                    tertiary_muscle,
                    other_muscles,
                )
                return {"id": eid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.put("/exercise_catalog/{name}")
        def update_exercise_catalog(
            name: str,
            muscle_group: str,
            variants: str,
            equipment_names: str,
            primary_muscle: str,
            secondary_muscle: str = "",
            tertiary_muscle: str = "",
            other_muscles: str = "",
            new_name: str = None,
        ):
            try:
                self.exercise_catalog.update(
                    name,
                    muscle_group,
                    variants,
                    equipment_names,
                    primary_muscle,
                    secondary_muscle,
                    tertiary_muscle,
                    other_muscles,
                    new_name,
                )
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/exercise_catalog/{name}")
        def delete_exercise_catalog(name: str):
            try:
                self.exercise_catalog.remove(name)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.put("/equipment/{name}")
        def update_equipment(
            name: str,
            equipment_type: str,
            muscles: str,
            new_name: str = None,
        ):
            try:
                self.equipment.update(
                    name, equipment_type, muscles.split("|"), new_name
                )
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/equipment/{name}")
        def delete_equipment(name: str):
            try:
                self.equipment.remove(name)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/workouts")
        def create_workout(date: str = None, training_type: str = "strength"):
            try:
                workout_date = (
                    datetime.date.today()
                    if date is None
                    else datetime.date.fromisoformat(date)
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid date format")
            if workout_date > datetime.date.today():
                raise HTTPException(status_code=400, detail="date cannot be in the future")
            workout_id = self.workouts.create(
                workout_date.isoformat(), training_type
            )
            return {"id": workout_id}

        @self.app.get("/workouts")
        def list_workouts(start_date: str = None, end_date: str = None):
            workouts = self.workouts.fetch_all_workouts(start_date, end_date)
            return [{"id": wid, "date": date} for wid, date, *_ in workouts]

        @self.app.get("/workouts/history")
        def workout_history(
            start_date: str,
            end_date: str,
            training_type: str = None,
        ):
            workouts = self.workouts.fetch_all_workouts(start_date, end_date)
            result = []
            for wid, date, _s, _e, t_type in workouts:
                if training_type and t_type != training_type:
                    continue
                summary = self.sets.workout_summary(wid)
                result.append(
                    {
                        "id": wid,
                        "date": date,
                        "training_type": t_type,
                        "volume": summary["volume"],
                        "sets": summary["sets"],
                        "avg_rpe": summary["avg_rpe"],
                    }
                )
            return result

        @self.app.get("/workouts/{workout_id}")
        def get_workout(workout_id: int):
            wid, date, start_time, end_time, training_type = self.workouts.fetch_detail(workout_id)
            return {
                "id": wid,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "training_type": training_type,
            }

        @self.app.get("/workouts/{workout_id}/export_csv")
        def export_workout_csv(workout_id: int):
            data = self.sets.export_workout_csv(workout_id)
            return Response(
                content=data,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=workout_{workout_id}.csv"
                },
            )

        @self.app.put("/workouts/{workout_id}/type")
        def update_workout_type(workout_id: int, training_type: str):
            self.workouts.set_training_type(workout_id, training_type)
            return {"status": "updated"}

        @self.app.post("/workouts/{workout_id}/start")
        def start_workout(workout_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.workouts.set_start_time(workout_id, timestamp)
            return {"status": "started", "timestamp": timestamp}

        @self.app.post("/workouts/{workout_id}/finish")
        def finish_workout(workout_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.workouts.set_end_time(workout_id, timestamp)
            return {"status": "finished", "timestamp": timestamp}

        @self.app.post("/workouts/{workout_id}/exercises")
        def add_exercise(workout_id: int, name: str, equipment: str):
            if not equipment:
                raise HTTPException(status_code=400, detail="equipment required")
            ex_id = self.exercises.add(workout_id, name, equipment)
            return {"id": ex_id}

        @self.app.delete("/exercises/{exercise_id}")
        def delete_exercise(exercise_id: int):
            self.exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.get("/workouts/{workout_id}/exercises")
        def list_exercises(workout_id: int):
            exercises = self.exercises.fetch_for_workout(workout_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq}
                for ex_id, name, eq in exercises
            ]

        @self.app.post("/planned_workouts")
        def create_planned_workout(date: str, training_type: str = "strength"):
            plan_id = self.planned_workouts.create(date, training_type)
            return {"id": plan_id}

        @self.app.get("/planned_workouts")
        def list_planned_workouts():
            plans = self.planned_workouts.fetch_all()
            return [
                {"id": pid, "date": date, "training_type": t}
                for pid, date, t in plans
            ]

        @self.app.put("/planned_workouts/{plan_id}")
        def update_planned_workout(
            plan_id: int,
            date: str | None = None,
            training_type: str | None = None,
        ):
            try:
                if date is not None:
                    self.planned_workouts.update_date(plan_id, date)
                if training_type is not None:
                    self.planned_workouts.set_training_type(plan_id, training_type)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/planned_workouts/{plan_id}")
        def delete_planned_workout(plan_id: int):
            try:
                self.planned_workouts.delete(plan_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/planned_workouts/{plan_id}/duplicate")
        def duplicate_planned_workout(plan_id: int, date: str):
            try:
                new_id = self.planner.duplicate_plan(plan_id, date)
                return {"id": new_id}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/planned_workouts/{plan_id}/exercises")
        def add_planned_exercise(plan_id: int, name: str, equipment: str):
            if not equipment:
                raise HTTPException(status_code=400, detail="equipment required")
            ex_id = self.planned_exercises.add(plan_id, name, equipment)
            return {"id": ex_id}

        @self.app.get("/planned_workouts/{plan_id}/exercises")
        def list_planned_exercises(plan_id: int):
            exercises = self.planned_exercises.fetch_for_workout(plan_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq}
                for ex_id, name, eq in exercises
            ]

        @self.app.delete("/planned_exercises/{exercise_id}")
        def delete_planned_exercise(exercise_id: int):
            self.planned_exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.post("/planned_exercises/{exercise_id}/sets")
        def add_planned_set(exercise_id: int, reps: int, weight: float, rpe: int):
            set_id = self.planned_sets.add(exercise_id, reps, weight, rpe)
            return {"id": set_id}

        @self.app.get("/planned_exercises/{exercise_id}/sets")
        def list_planned_sets(exercise_id: int):
            sets = self.planned_sets.fetch_for_exercise(exercise_id)
            return [
                {"id": sid, "reps": reps, "weight": weight, "rpe": rpe}
                for sid, reps, weight, rpe in sets
            ]

        @self.app.put("/planned_sets/{set_id}")
        def update_planned_set(set_id: int, reps: int, weight: float, rpe: int):
            self.planned_sets.update(set_id, reps, weight, rpe)
            return {"status": "updated"}

        @self.app.get("/planned_sets/{set_id}")
        def get_planned_set(set_id: int):
            try:
                return self.planned_sets.fetch_detail(set_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.delete("/planned_sets/{set_id}")
        def delete_planned_set(set_id: int):
            self.planned_sets.remove(set_id)
            return {"status": "deleted"}

        @self.app.post("/planned_workouts/{plan_id}/use")
        def use_planned_workout(plan_id: int):
            workout_id = self.planner.create_workout_from_plan(plan_id)
            return {"id": workout_id}

        @self.app.post("/exercises/{exercise_id}/sets")
        def add_set(exercise_id: int, reps: int, weight: float, rpe: int):
            set_id = self.sets.add(exercise_id, reps, weight, rpe)
            try:
                self.gamification.record_set(exercise_id, reps, weight, rpe)
            except Exception:
                pass
            return {"id": set_id}

        @self.app.put("/sets/{set_id}")
        def update_set(set_id: int, reps: int, weight: float, rpe: int):
            self.sets.update(set_id, reps, weight, rpe)
            return {"status": "updated"}

        @self.app.delete("/sets/{set_id}")
        def delete_set(set_id: int):
            self.sets.remove(set_id)
            return {"status": "deleted"}

        @self.app.post("/sets/{set_id}/start")
        def start_set(set_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.sets.set_start_time(set_id, timestamp)
            return {"status": "started", "timestamp": timestamp}

        @self.app.post("/sets/{set_id}/finish")
        def finish_set(set_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.sets.set_end_time(set_id, timestamp)
            return {"status": "finished", "timestamp": timestamp}

        @self.app.get("/sets/{set_id}")
        def get_set(set_id: int):
            return self.sets.fetch_detail(set_id)

        @self.app.get("/exercises/{exercise_id}/sets")
        def list_sets(exercise_id: int):
            sets = self.sets.fetch_for_exercise(exercise_id)
            result = []
            for sid, reps, weight, rpe, start_time, end_time in sets:
                entry = {
                    "id": sid,
                    "reps": reps,
                    "weight": weight,
                    "rpe": rpe,
                }
                if start_time is not None:
                    entry["start_time"] = start_time
                if end_time is not None:
                    entry["end_time"] = end_time
                result.append(entry)
            return result

        @self.app.post("/exercises/{exercise_id}/recommend_next")
        def recommend_next(exercise_id: int):
            try:
                return self.recommender.recommend_next_set(exercise_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/stats/exercise_history")
        def stats_exercise_history(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.exercise_history(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/exercise_summary")
        def stats_exercise_summary(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.exercise_summary(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/progression")
        def stats_progression(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.progression(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/daily_volume")
        def stats_daily_volume(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.daily_volume(start_date, end_date)

        @self.app.get("/stats/equipment_usage")
        def stats_equipment_usage(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.equipment_usage(start_date, end_date)

        @self.app.get("/stats/rpe_distribution")
        def stats_rpe_distribution(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.rpe_distribution(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/reps_distribution")
        def stats_reps_distribution(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.reps_distribution(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/overview")
        def stats_overview(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.overview(start_date, end_date)

        @self.app.get("/stats/personal_records")
        def stats_personal_records(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.personal_records(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/training_stress")
        def stats_training_stress(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.training_stress(start_date, end_date)

        @self.app.get("/stats/load_variability")
        def stats_load_variability(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.weekly_load_variability(start_date, end_date)

        @self.app.get("/gamification")
        def gamification_status():
            return {
                "enabled": self.gamification.is_enabled(),
                "points": self.gamification.total_points(),
            }

        @self.app.post("/gamification/enable")
        def gamification_enable(enabled: bool = True):
            self.gamification.enable(enabled)
            return {"status": "updated"}

        @self.app.get("/stats/progress_insights")
        def stats_progress_insights(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.progress_insights(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/prediction/progress")
        def prediction_progress(
            exercise: str,
            weeks: int,
            workouts: int,
        ):
            return self.statistics.progress_forecast(
                exercise,
                weeks,
                workouts,
            )

        @self.app.post("/pyramid_tests")
        def create_pyramid_test(
            weights: str,
            date: str = None,
            exercise_name: str = "Unknown",
            equipment_name: str | None = None,
            starting_weight: float | None = None,
            failed_weight: float | None = None,
            max_achieved: float | None = None,
            test_duration_minutes: int | None = None,
            rest_between_attempts: str | None = None,
            rpe_per_attempt: str | None = None,
            time_of_day: str | None = None,
            sleep_hours: float | None = None,
            stress_level: int | None = None,
            nutrition_quality: int | None = None,
        ):
            try:
                test_date = (
                    datetime.date.today()
                    if date is None
                    else datetime.date.fromisoformat(date)
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid date format")
            values = [float(w) for w in weights.split("|") if w]
            if not values:
                raise HTTPException(status_code=400, detail="weights required")

            data = {
                "exercise_name": exercise_name,
                "date": test_date.isoformat(),
                "equipment_name": equipment_name,
                "starting_weight": starting_weight or values[0],
                "successful_weights": values,
                "failed_weight": failed_weight,
                "max_achieved": max_achieved or max(values),
                "test_duration_minutes": test_duration_minutes,
                "rest_between_attempts": rest_between_attempts,
                "rpe_per_attempt": rpe_per_attempt,
                "time_of_day": time_of_day,
                "sleep_hours": sleep_hours,
                "stress_level": stress_level,
                "nutrition_quality": nutrition_quality,
            }
            if not ExercisePrescription._validate_pyramid_test(data):
                raise HTTPException(status_code=400, detail="invalid pyramid test")
            tid = self.pyramid_tests.create(
                test_date.isoformat(),
                exercise_name=exercise_name,
                equipment_name=equipment_name,
                starting_weight=data["starting_weight"],
                failed_weight=failed_weight,
                max_achieved=data["max_achieved"],
                test_duration_minutes=test_duration_minutes,
                rest_between_attempts=rest_between_attempts,
                rpe_per_attempt=rpe_per_attempt,
                time_of_day=time_of_day,
                sleep_hours=sleep_hours,
                stress_level=stress_level,
                nutrition_quality=nutrition_quality,
            )
            for w in values:
                self.pyramid_entries.add(tid, w)
            return {"id": tid}

        @self.app.get("/pyramid_tests")
        def list_pyramid_tests():
            tests = self.pyramid_tests.fetch_all_with_weights(self.pyramid_entries)
            return [
                {"id": tid, "date": date, "weights": weights} for tid, date, weights in tests
            ]

        @self.app.get("/pyramid_tests/full")
        def list_pyramid_tests_full():
            tests = self.pyramid_tests.fetch_full_with_weights(self.pyramid_entries)
            result = []
            for row in tests:
                (
                    tid,
                    name,
                    date,
                    eq_name,
                    start_w,
                    failed_w,
                    max_a,
                    dur,
                    rest,
                    rpe_attempt,
                    tod,
                    sleep_h,
                    stress,
                    nutrition,
                    weights,
                ) = row
                result.append(
                    {
                        "id": tid,
                        "exercise_name": name,
                        "date": date,
                        "equipment_name": eq_name,
                        "starting_weight": start_w,
                        "failed_weight": failed_w,
                        "max_achieved": max_a,
                        "test_duration_minutes": dur,
                        "rest_between_attempts": rest,
                        "rpe_per_attempt": rpe_attempt,
                        "time_of_day": tod,
                        "sleep_hours": sleep_h,
                        "stress_level": stress,
                        "nutrition_quality": nutrition,
                        "weights": weights,
                    }
                )
            return result

        @self.app.get("/settings/general")
        def get_general_settings():
            return self.settings.all_settings()

        @self.app.post("/settings/general")
        def update_general_settings(
            body_weight: float = None,
            months_active: float = None,
            theme: str = None,
        ):
            if body_weight is not None:
                self.settings.set_float("body_weight", body_weight)
            if months_active is not None:
                self.settings.set_float("months_active", months_active)
            if theme is not None:
                self.settings.set_text("theme", theme)
            return {"status": "updated"}

        @self.app.post("/settings/delete_all")
        def delete_all(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.workouts.delete_all()
            self.planned_workouts.delete_all()
            return {"status": "deleted"}

        @self.app.post("/settings/delete_logged")
        def delete_logged(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.workouts.delete_all()
            return {"status": "deleted"}

        @self.app.post("/settings/delete_planned")
        def delete_planned(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.planned_workouts.delete_all()
            return {"status": "deleted"}


api = GymAPI()
app = api.app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
