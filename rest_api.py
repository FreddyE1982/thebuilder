import datetime
from fastapi import FastAPI, HTTPException, Response
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    TemplateWorkoutRepository,
    TemplateExerciseRepository,
    TemplateSetRepository,
    EquipmentRepository,
    EquipmentTypeRepository,
    ExerciseCatalogRepository,
    MuscleRepository,
    MuscleGroupRepository,
    ExerciseNameRepository,
    ExerciseVariantRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
    GamificationRepository,
    MLModelRepository,
    MLLogRepository,
    MLModelStatusRepository,
    AutoPlannerLogRepository,
    ExercisePrescriptionLogRepository,
    BodyWeightRepository,
    WellnessRepository,
    HeartRateRepository,
    FavoriteExerciseRepository,
    FavoriteTemplateRepository,
    FavoriteWorkoutRepository,
    TagRepository,
    GoalRepository,
)
from planner_service import PlannerService
from recommendation_service import RecommendationService
from stats_service import StatisticsService
from gamification_service import GamificationService
from ml_service import (
    PerformanceModelService,
    VolumeModelService,
    ReadinessModelService,
    ProgressModelService,
    RLGoalModelService,
    InjuryRiskModelService,
    AdaptationModelService,
)
from tools import ExercisePrescription, MathTools, GitTools


class GymAPI:
    """Provides REST endpoints for workout logging."""

    def __init__(
        self, db_path: str = "workout.db", yaml_path: str = "settings.yaml"
    ) -> None:
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.planned_workouts = PlannedWorkoutRepository(db_path)
        self.planned_exercises = PlannedExerciseRepository(db_path)
        self.planned_sets = PlannedSetRepository(db_path)
        self.template_workouts = TemplateWorkoutRepository(db_path)
        self.template_exercises = TemplateExerciseRepository(db_path)
        self.template_sets = TemplateSetRepository(db_path)
        self.settings = SettingsRepository(db_path, yaml_path)
        self.equipment_types = EquipmentTypeRepository(db_path, self.settings)
        self.equipment = EquipmentRepository(db_path, self.settings, self.equipment_types)
        self.exercise_catalog = ExerciseCatalogRepository(db_path, self.settings)
        self.muscles = MuscleRepository(db_path)
        self.muscle_groups = MuscleGroupRepository(db_path, self.muscles)
        self.exercise_names = ExerciseNameRepository(db_path)
        self.exercise_variants = ExerciseVariantRepository(db_path)
        self.favorites = FavoriteExerciseRepository(db_path)
        self.favorite_templates = FavoriteTemplateRepository(db_path)
        self.favorite_workouts = FavoriteWorkoutRepository(db_path)
        self.tags = TagRepository(db_path)
        self.pyramid_tests = PyramidTestRepository(db_path)
        self.pyramid_entries = PyramidEntryRepository(db_path)
        self.game_repo = GamificationRepository(db_path)
        self.ml_models = MLModelRepository(db_path)
        self.ml_logs = MLLogRepository(db_path)
        self.ml_status = MLModelStatusRepository(db_path)
        self.autoplan_logs = AutoPlannerLogRepository(db_path)
        self.prescription_logs = ExercisePrescriptionLogRepository(db_path)
        self.body_weights = BodyWeightRepository(db_path)
        self.wellness = WellnessRepository(db_path)
        self.heart_rates = HeartRateRepository(db_path)
        self.goals = GoalRepository(db_path)
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings,
            self.workouts,
        )
        self.ml_service = PerformanceModelService(
            self.ml_models,
            self.exercise_names,
            self.ml_logs,
            self.ml_status,
        )
        self.volume_model = VolumeModelService(self.ml_models, status_repo=self.ml_status)
        self.readiness_model = ReadinessModelService(self.ml_models, status_repo=self.ml_status)
        self.progress_model = ProgressModelService(self.ml_models, status_repo=self.ml_status)
        self.goal_model = RLGoalModelService(self.ml_models, status_repo=self.ml_status)
        self.injury_model = InjuryRiskModelService(self.ml_models, status_repo=self.ml_status)
        self.adaptation_model = AdaptationModelService(self.ml_models, status_repo=self.ml_status)
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names,
            self.settings,
            self.gamification,
            self.ml_service,
            self.goal_model,
            self.body_weights,
            self.goals,
            self.wellness,
            prescription_log_repo=self.prescription_logs,
        )
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
            self.gamification,
            self.template_workouts,
            self.template_exercises,
            self.template_sets,
            recommender=self.recommender,
            log_repo=self.autoplan_logs,
        )
        self.statistics = StatisticsService(
            self.sets,
            self.exercise_names,
            self.settings,
            self.volume_model,
            self.readiness_model,
            self.progress_model,
            self.injury_model,
            self.adaptation_model,
            self.body_weights,
            self.equipment,
            self.wellness,
            self.exercise_catalog,
            self.workouts,
            self.heart_rates,
        )
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/health")
        def health():
            """Return API and database connection status."""
            try:
                # simple query to verify database connectivity
                self.workouts.fetch_all_workouts()
                return {"status": "ok"}
            except Exception as e:  # pragma: no cover - connectivity failure
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/equipment/types")
        def list_equipment_types():
            return self.equipment.fetch_types()

        @self.app.post("/equipment/types")
        def add_equipment_type(name: str):
            try:
                tid = self.equipment_types.add(name)
                return {"id": tid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/equipment")
        def list_equipment(
            equipment_type: str = None,
            prefix: str = None,
            muscles: str = None,
        ):
            muscs = muscles.split("|") if muscles else None
            return self.equipment.fetch_names(equipment_type, prefix, muscs)

        @self.app.get("/equipment/recent")
        def recent_equipment(limit: int = 5):
            return self.statistics.recent_equipment(limit)

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
                eid = self.equipment.add(equipment_type, name, muscles.split("|"))
                return {"id": eid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/muscles")
        def list_muscles():
            return self.muscles.fetch_all()

        @self.app.get("/muscles/recent")
        def recent_muscles(limit: int = 5):
            return self.statistics.recent_muscles(limit)

        @self.app.post("/muscles")
        def add_muscle(name: str):
            try:
                self.muscles.add(name)
                return {"status": "added"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/muscles/link")
        def link_muscles(name1: str, name2: str):
            self.muscles.link(name1, name2)
            return {"status": "linked"}

        @self.app.post("/muscles/alias")
        def add_alias(new_name: str, existing: str):
            self.muscles.add_alias(new_name, existing)
            return {"status": "added"}

        @self.app.get("/muscle_groups")
        def list_muscle_groups():
            return self.muscle_groups.fetch_all()

        @self.app.post("/muscle_groups")
        def add_muscle_group(name: str):
            try:
                self.muscle_groups.add(name)
                return {"status": "added"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.put("/muscle_groups/{group}")
        def rename_muscle_group(group: str, new_name: str):
            try:
                self.muscle_groups.rename(group, new_name)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.delete("/muscle_groups/{group}")
        def delete_muscle_group(group: str):
            try:
                self.muscle_groups.delete(group)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.get("/muscle_groups/{group}/muscles")
        def list_group_muscles(group: str):
            return self.muscle_groups.fetch_muscles(group)

        @self.app.post("/muscle_groups/{group}/muscles")
        def assign_muscle_group(group: str, muscle: str):
            try:
                self.muscle_groups.assign(group, muscle)
                return {"status": "assigned"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/muscles/{muscle}/group")
        def remove_muscle_group(muscle: str):
            self.muscle_groups.remove_assignment(muscle)
            return {"status": "removed"}

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

        @self.app.post("/exercise_variants/link")
        def link_exercise_variant(name: str, variant: str):
            self.exercise_variants.link(name, variant)
            return {"status": "linked"}

        @self.app.delete("/exercise_variants/link")
        def unlink_exercise_variant(name: str, variant: str):
            self.exercise_variants.unlink(name, variant)
            return {"status": "unlinked"}

        @self.app.get("/exercise_variants/{name}")
        def list_exercise_variants(name: str):
            return self.exercise_variants.fetch_variants(name)

        @self.app.get("/favorites/exercises")
        def list_favorite_exercises():
            return self.favorites.fetch_all()

        @self.app.post("/favorites/exercises")
        def add_favorite_exercise(name: str):
            self.favorites.add(name)
            return {"status": "added"}

        @self.app.delete("/favorites/exercises/{name}")
        def delete_favorite_exercise(name: str):
            self.favorites.remove(name)
            return {"status": "deleted"}

        @self.app.get("/favorites/templates")
        def list_favorite_templates():
            return self.favorite_templates.fetch_all()

        @self.app.post("/favorites/templates")
        def add_favorite_template(template_id: int):
            self.favorite_templates.add(template_id)
            return {"status": "added"}

        @self.app.delete("/favorites/templates/{template_id}")
        def delete_favorite_template(template_id: int):
            self.favorite_templates.remove(template_id)
            return {"status": "deleted"}

        @self.app.get("/favorites/workouts")
        def list_favorite_workouts():
            return self.favorite_workouts.fetch_all()

        @self.app.post("/favorites/workouts")
        def add_favorite_workout(workout_id: int):
            self.favorite_workouts.add(workout_id)
            return {"status": "added"}

        @self.app.delete("/favorites/workouts/{workout_id}")
        def delete_favorite_workout(workout_id: int):
            self.favorite_workouts.remove(workout_id)
            return {"status": "deleted"}

        @self.app.get("/tags")
        def list_tags():
            rows = self.tags.fetch_all()
            return [{"id": tid, "name": name} for tid, name in rows]

        @self.app.post("/tags")
        def add_tag(name: str):
            tid = self.tags.add(name)
            return {"id": tid}

        @self.app.put("/tags/{tag_id}")
        def update_tag(tag_id: int, name: str):
            try:
                self.tags.update(tag_id, name)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.delete("/tags/{tag_id}")
        def delete_tag(tag_id: int):
            try:
                self.tags.delete(tag_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.get("/workouts/{workout_id}/tags")
        def list_workout_tags(workout_id: int):
            rows = self.tags.fetch_for_workout(workout_id)
            return [{"id": tid, "name": name} for tid, name in rows]

        @self.app.post("/workouts/{workout_id}/tags")
        def add_workout_tag(workout_id: int, tag_id: int):
            self.tags.assign(workout_id, tag_id)
            return {"status": "added"}

        @self.app.delete("/workouts/{workout_id}/tags/{tag_id}")
        def remove_workout_tag(workout_id: int, tag_id: int):
            self.tags.remove(workout_id, tag_id)
            return {"status": "deleted"}

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
                "equipment_names": (
                    equipment_names.split("|") if equipment_names else []
                ),
                "primary_muscle": primary_muscle,
                "secondary_muscle": (
                    secondary_muscle.split("|") if secondary_muscle else []
                ),
                "tertiary_muscle": (
                    tertiary_muscle.split("|") if tertiary_muscle else []
                ),
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
        def create_workout(
            date: str = None,
            training_type: str = "strength",
            notes: str | None = None,
            location: str | None = None,
            rating: int | None = None,
        ):
            try:
                workout_date = (
                    datetime.date.today()
                    if date is None
                    else datetime.date.fromisoformat(date)
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid date format")
            if workout_date > datetime.date.today():
                raise HTTPException(
                    status_code=400, detail="date cannot be in the future"
                )
            workout_id = self.workouts.create(
                workout_date.isoformat(),
                training_type,
                notes,
                location,
                rating,
            )
            return {"id": workout_id}

        @self.app.get("/workouts")
        def list_workouts(
            start_date: str = None,
            end_date: str = None,
            sort_by: str = "id",
            descending: bool = True,
        ):
            workouts = self.workouts.fetch_all_workouts(
                start_date, end_date, sort_by, descending
            )
            return [{"id": wid, "date": date} for wid, date, *_ in workouts]

        @self.app.get("/workouts/search")
        def search_workouts(query: str):
            rows = self.workouts.search(query)
            return [{"id": wid, "date": date} for wid, date in rows]

        @self.app.get("/workouts/history")
        def workout_history(
            start_date: str,
            end_date: str,
            training_type: str = None,
        ):
            workouts = self.workouts.fetch_all_workouts(start_date, end_date)
            result = []
            for wid, date, _s, _e, t_type, _notes, _rating in workouts:
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

        @self.app.get("/calendar")
        def calendar(start_date: str, end_date: str):
            logged = self.workouts.fetch_all_workouts(start_date, end_date)
            planned = self.planned_workouts.fetch_all(start_date, end_date)
            result = []
            for wid, date, _s, _e, t_type, _notes, _rating in logged:
                result.append(
                    {
                        "id": wid,
                        "date": date,
                        "training_type": t_type,
                        "planned": False,
                    }
                )
            for pid, date, t_type in planned:
                result.append(
                    {
                        "id": pid,
                        "date": date,
                        "training_type": t_type,
                        "planned": True,
                    }
                )
            result.sort(key=lambda x: x["date"])
            return result

        @self.app.get("/workouts/{workout_id}")
        def get_workout(workout_id: int):
            (
                wid,
                date,
                start_time,
                end_time,
                training_type,
                notes,
                location,
                rating,
            ) = self.workouts.fetch_detail(workout_id)
            return {
                "id": wid,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "training_type": training_type,
                "notes": notes,
                "location": location,
                "rating": rating,
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

        @self.app.get("/workouts/{workout_id}/export_json")
        def export_workout_json(workout_id: int):
            data = self.sets.export_workout_json(workout_id)
            return Response(
                content=data,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=workout_{workout_id}.json"
                },
            )

        @self.app.put("/workouts/{workout_id}/type")
        def update_workout_type(workout_id: int, training_type: str):
            self.workouts.set_training_type(workout_id, training_type)
            return {"status": "updated"}

        @self.app.put("/workouts/{workout_id}/note")
        def update_workout_note(workout_id: int, notes: str = None):
            self.workouts.set_note(workout_id, notes)
            return {"status": "updated"}

        @self.app.put("/workouts/{workout_id}/location")
        def update_workout_location(workout_id: int, location: str = None):
            self.workouts.set_location(workout_id, location)
            return {"status": "updated"}

        @self.app.put("/workouts/{workout_id}/rating")
        def update_workout_rating(workout_id: int, rating: int | None = None):
            self.workouts.set_rating(workout_id, rating)
            return {"status": "updated"}

        @self.app.delete("/workouts/{workout_id}")
        def delete_workout(workout_id: int):
            try:
                self.workouts.delete(workout_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.post("/workouts/{workout_id}/start")
        def start_workout(workout_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.workouts.set_start_time(workout_id, timestamp)
            return {"status": "started", "timestamp": timestamp}

        @self.app.post("/workouts/{workout_id}/finish")
        def finish_workout(workout_id: int):
            timestamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.workouts.set_end_time(workout_id, timestamp)
            if (
                self.statistics.volume_model is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_training_enabled", True)
                and self.settings.get_bool("ml_volume_training_enabled", True)
            ):
                daily = self.statistics.daily_volume()
                vols = [d["volume"] for d in daily]
                if len(vols) >= 4:
                    feats = vols[-4:-1]
                    target = vols[-1]
                    self.statistics.volume_model.train(feats, target)
            if (
                self.statistics.readiness_model is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_training_enabled", True)
                and self.settings.get_bool("ml_readiness_training_enabled", True)
            ):
                stress_data = self.statistics.training_stress(
                    start_date=None, end_date=None
                )
                if stress_data:
                    s = stress_data[-1]
                    score = MathTools.readiness_score(s["stress"], s["fatigue"] / 1000)
                    self.statistics.readiness_model.train(
                        s["stress"], s["fatigue"], score
                    )
            return {"status": "finished", "timestamp": timestamp}

        @self.app.post("/workouts/{workout_id}/exercises")
        def add_exercise(
            workout_id: int, name: str, equipment: str, note: str | None = None
        ):
            if not equipment:
                raise HTTPException(status_code=400, detail="equipment required")
            ex_id = self.exercises.add(workout_id, name, equipment, note)
            return {"id": ex_id}

        @self.app.delete("/exercises/{exercise_id}")
        def delete_exercise(exercise_id: int):
            self.exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.get("/exercises/{exercise_id}")
        def get_exercise(exercise_id: int):
            try:
                wid, name, equipment, note = self.exercises.fetch_detail(exercise_id)
                return {
                    "id": exercise_id,
                    "workout_id": wid,
                    "name": name,
                    "equipment": equipment,
                    "note": note,
                }
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.put("/exercises/{exercise_id}/note")
        def update_exercise_note(exercise_id: int, note: str | None = None):
            self.exercises.update_note(exercise_id, note)
            return {"status": "updated"}

        @self.app.put("/exercises/{exercise_id}/name")
        def update_exercise_name(exercise_id: int, name: str):
            self.exercises.update_name(exercise_id, name)
            return {"status": "updated"}

        @self.app.get("/workouts/{workout_id}/exercises")
        def list_exercises(workout_id: int):
            exercises = self.exercises.fetch_for_workout(workout_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq, "note": note}
                for ex_id, name, eq, note in exercises
            ]

        @self.app.post("/planned_workouts")
        def create_planned_workout(date: str, training_type: str = "strength"):
            plan_id = self.planned_workouts.create(date, training_type)
            return {"id": plan_id}

        @self.app.get("/planned_workouts")
        def list_planned_workouts(
            start_date: str = None,
            end_date: str = None,
            sort_by: str = "id",
            descending: bool = True,
        ):
            plans = self.planned_workouts.fetch_all(
                start_date, end_date, sort_by, descending
            )
            return [
                {"id": pid, "date": date, "training_type": t} for pid, date, t in plans
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

        @self.app.post("/workouts/{workout_id}/copy_to_template")
        def copy_workout_to_template(workout_id: int, name: str = None):
            try:
                tid = self.planner.copy_workout_to_template(workout_id, name)
                return {"id": tid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/planned_workouts/auto_plan")
        def auto_plan(date: str, exercises: str, training_type: str = "strength"):
            items = [i for i in exercises.split("|") if i]
            pairs: list[tuple[str, str | None]] = []
            for it in items:
                if "@" in it:
                    n, eq = it.split("@", 1)
                    pairs.append((n, eq or None))
                else:
                    pairs.append((it, None))
            try:
                pid = self.planner.create_ai_plan(date, pairs, training_type)
                return {"id": pid}
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

        @self.app.post("/templates")
        def create_template(name: str, training_type: str = "strength"):
            tid = self.template_workouts.create(name, training_type)
            return {"id": tid}

        @self.app.get("/templates")
        def list_templates():
            templates = self.template_workouts.fetch_all()
            return [
                {"id": tid, "name": name, "training_type": t}
                for tid, name, t in templates
            ]

        @self.app.put("/templates/{template_id}")
        def update_template(
            template_id: int,
            name: str | None = None,
            training_type: str | None = None,
        ):
            try:
                self.template_workouts.update(template_id, name, training_type)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/templates/{template_id}")
        def delete_template(template_id: int):
            try:
                self.template_workouts.delete(template_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/templates/{template_id}/exercises")
        def add_template_exercise(template_id: int, name: str, equipment: str):
            ex_id = self.template_exercises.add(template_id, name, equipment)
            return {"id": ex_id}

        @self.app.get("/templates/{template_id}/exercises")
        def list_template_exercises(template_id: int):
            exercises = self.template_exercises.fetch_for_template(template_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq}
                for ex_id, name, eq in exercises
            ]

        @self.app.delete("/template_exercises/{exercise_id}")
        def delete_template_exercise(exercise_id: int):
            self.template_exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.post("/template_exercises/{exercise_id}/sets")
        def add_template_set(exercise_id: int, reps: int, weight: float, rpe: int):
            sid = self.template_sets.add(exercise_id, reps, weight, rpe)
            return {"id": sid}

        @self.app.get("/template_exercises/{exercise_id}/sets")
        def list_template_sets(exercise_id: int):
            sets = self.template_sets.fetch_for_exercise(exercise_id)
            return [
                {"id": sid, "reps": reps, "weight": weight, "rpe": rpe}
                for sid, reps, weight, rpe in sets
            ]

        @self.app.post("/templates/{template_id}/plan")
        def create_plan_from_template(template_id: int, date: str):
            try:
                plan_id = self.planner.create_plan_from_template(template_id, date)
                return {"id": plan_id}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/exercises/{exercise_id}/sets")
        def add_set(
            exercise_id: int,
            reps: int,
            weight: float,
            rpe: int,
            note: str | None = None,
            warmup: bool = False,
        ):
            prev = self.sets.last_rpe(exercise_id)
            try:
                set_id = self.sets.add(
                    exercise_id, reps, weight, rpe, note, warmup=warmup
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            _, name, _, _ = self.exercises.fetch_detail(exercise_id)
            if (
                self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_training_enabled", True)
                and self.settings.get_bool("ml_rpe_training_enabled", True)
            ):
                self.ml_service.train(
                    name,
                    reps,
                    weight,
                    rpe,
                    prev if prev is not None else rpe,
                )
            try:
                self.gamification.record_set(exercise_id, reps, weight, rpe)
            except Exception:
                pass
            self.recommender.record_result(set_id, reps, weight, rpe)
            return {"id": set_id}

        @self.app.post("/exercises/{exercise_id}/bulk_sets")
        def bulk_add_sets(exercise_id: int, sets: str):
            lines = [l.strip() for l in sets.split("|") if l.strip()]
            entries: list[tuple[int, float, int]] = []
            for line in lines:
                try:
                    r_s, w_s, rpe_s = [p.strip() for p in line.split(",")]
                    entries.append((int(r_s), float(w_s), int(rpe_s)))
                except Exception:
                    raise HTTPException(status_code=400, detail="invalid format")
            try:
                ids = self.sets.bulk_add(exercise_id, entries)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            for rid, (reps_i, weight_i, rpe_i) in zip(ids, entries):
                self.recommender.record_result(rid, reps_i, weight_i, rpe_i)
            return {"added": len(ids)}

        @self.app.post("/exercises/{exercise_id}/warmup_sets")
        def add_warmup_sets(
            exercise_id: int,
            target_weight: float,
            target_reps: int,
            sets: int = 3,
        ):
            try:
                plan = MathTools.warmup_plan(target_weight, target_reps, sets)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            ids: list[int] = []
            for reps_i, weight_i in plan:
                sid = self.sets.add(
                    exercise_id,
                    int(reps_i),
                    float(weight_i),
                    6,
                    warmup=True,
                )
                self.recommender.record_result(sid, int(reps_i), float(weight_i), 6)
                try:
                    self.gamification.record_set(exercise_id, int(reps_i), float(weight_i), 6)
                except Exception:
                    pass
                ids.append(sid)
            return {"added": len(ids), "ids": ids}

        @self.app.put("/sets/{set_id}")
        def update_set(
            set_id: int, reps: int, weight: float, rpe: int, warmup: bool | None = None
        ):
            prev = self.sets.previous_rpe(set_id)
            try:
                self.sets.update(set_id, reps, weight, rpe, warmup)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            ex_id = self.sets.fetch_exercise_id(set_id)
            _, name, _, _ = self.exercises.fetch_detail(ex_id)
            if (
                self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_training_enabled", True)
                and self.settings.get_bool("ml_rpe_training_enabled", True)
            ):
                self.ml_service.train(
                    name,
                    reps,
                    weight,
                    rpe,
                    prev if prev is not None else rpe,
                )
            self.recommender.record_result(set_id, reps, weight, rpe)
            return {"status": "updated"}

        @self.app.put("/sets/{set_id}/note")
        def update_set_note(set_id: int, note: str | None = None):
            self.sets.update_note(set_id, note)
            return {"status": "updated"}

        @self.app.delete("/sets/{set_id}")
        def delete_set(set_id: int):
            self.sets.remove(set_id)
            return {"status": "deleted"}

        @self.app.post("/sets/{set_id}/start")
        def start_set(set_id: int, timestamp: str | None = None):
            ts = (
                datetime.datetime.now().isoformat(timespec="seconds")
                if timestamp is None
                else timestamp
            )
            self.sets.set_start_time(set_id, ts)
            return {"status": "started", "timestamp": ts}

        @self.app.post("/sets/{set_id}/finish")
        def finish_set(set_id: int, timestamp: str | None = None):
            ts = (
                datetime.datetime.now().isoformat(timespec="seconds")
                if timestamp is None
                else timestamp
            )
            self.sets.set_end_time(set_id, ts)
            return {"status": "finished", "timestamp": ts}

        @self.app.post("/sets/{set_id}/duration")
        def set_duration(set_id: int, seconds: float, end: str | None = None):
            try:
                self.sets.set_duration(set_id, seconds, end)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            end_dt = (
                datetime.datetime.now()
                if end is None
                else datetime.datetime.fromisoformat(end)
            )
            start_dt = end_dt - datetime.timedelta(seconds=float(seconds))
            return {
                "status": "updated",
                "start_time": start_dt.isoformat(timespec="seconds"),
                "end_time": end_dt.isoformat(timespec="seconds"),
            }

        @self.app.get("/sets/{set_id}")
        def get_set(set_id: int):
            return self.sets.fetch_detail(set_id)

        @self.app.get("/exercises/{exercise_id}/sets")
        def list_sets(exercise_id: int):
            sets = self.sets.fetch_for_exercise(exercise_id)
            result = []
            for sid, reps, weight, rpe, start_time, end_time, warm in sets:
                entry = {
                    "id": sid,
                    "reps": reps,
                    "weight": weight,
                    "rpe": rpe,
                    "warmup": bool(warm),
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

        @self.app.get("/stats/muscle_usage")
        def stats_muscle_usage(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.muscle_usage(start_date, end_date)

        @self.app.get("/stats/muscle_group_usage")
        def stats_muscle_group_usage(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.muscle_group_usage(start_date, end_date)

        @self.app.get("/stats/daily_muscle_group_volume")
        def stats_daily_muscle_group_volume(
            muscle_group: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.daily_muscle_group_volume(
                muscle_group, start_date, end_date
            )

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

        @self.app.get("/stats/intensity_distribution")
        def stats_intensity_distribution(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.intensity_distribution(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/exercise_frequency")
        def stats_exercise_frequency(
            exercise: str = None,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.exercise_frequency(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/velocity_history")
        def stats_velocity_history(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.velocity_history(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/power_history")
        def stats_power_history(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.power_history(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/relative_power_history")
        def stats_relative_power_history(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.relative_power_history(
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

        @self.app.get("/stats/training_monotony")
        def stats_training_monotony(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.training_monotony(start_date, end_date)

        @self.app.get("/stats/training_strain")
        def stats_training_strain(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.training_strain(start_date, end_date)

        @self.app.get("/stats/weekly_volume_change")
        def stats_weekly_volume_change(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.weekly_volume_change(start_date, end_date)

        @self.app.get("/stats/stress_balance")
        def stats_stress_balance(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.stress_balance(start_date, end_date)

        @self.app.get("/stats/stress_overview")
        def stats_stress_overview(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.stress_overview(start_date, end_date)

        @self.app.get("/stats/session_efficiency")
        def stats_session_efficiency(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.session_efficiency(
                start_date,
                end_date,
            )
        @self.app.get("/stats/session_density")
        def stats_session_density(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.session_density(start_date, end_date)

        @self.app.get("/stats/set_pace")
        def stats_set_pace(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.set_pace(start_date, end_date)

        @self.app.get("/stats/rest_times")
        def stats_rest_times(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.rest_times(start_date, end_date)

        @self.app.get("/stats/session_duration")
        def stats_session_duration(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.session_duration(start_date, end_date)

        @self.app.get("/stats/time_under_tension")
        def stats_time_under_tension(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.time_under_tension(start_date, end_date)

        @self.app.get("/stats/exercise_diversity")
        def stats_exercise_diversity(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.exercise_diversity(start_date, end_date)

        @self.app.get("/stats/location_summary")
        def stats_location_summary(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.location_summary(start_date, end_date)

        @self.app.get("/stats/training_type_summary")
        def stats_training_type_summary(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.training_type_summary(start_date, end_date)

        @self.app.get("/stats/workout_consistency")
        def stats_workout_consistency(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.workout_consistency(start_date, end_date)

        @self.app.get("/stats/volume_forecast")
        def stats_volume_forecast(
            days: int = 7,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.volume_forecast(days, start_date, end_date)

        @self.app.get("/stats/overtraining_risk")
        def stats_overtraining_risk(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.overtraining_risk(start_date, end_date)

        @self.app.get("/stats/injury_risk")
        def stats_injury_risk(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.injury_risk(start_date, end_date)

        @self.app.get("/stats/readiness")
        def stats_readiness(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.readiness(start_date, end_date)

        @self.app.get("/stats/adaptation_index")
        def stats_adaptation_index(
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.adaptation_index(start_date, end_date)

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

        @self.app.get("/gamification/workout_points")
        def gamification_workout_points():
            return [
                {"workout_id": wid, "points": pts}
                for wid, pts in self.gamification.points_by_workout()
            ]

        @self.app.get("/gamification/streak")
        def gamification_streak():
            return self.gamification.workout_streak()

        @self.app.get("/utils/warmup_weights")
        def utils_warmup_weights(target_weight: float, sets: int = 3):
            try:
                weights = MathTools.warmup_weights(target_weight, sets)
                return {"weights": weights}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/utils/warmup_plan")
        def utils_warmup_plan(
            target_weight: float, target_reps: int, sets: int = 3
        ):
            try:
                plan = MathTools.warmup_plan(target_weight, target_reps, sets)
                return {
                    "plan": [
                        {"reps": r, "weight": w} for r, w in plan
                    ]
                }
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

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

        @self.app.get("/stats/advanced_plateau")
        def stats_advanced_plateau(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.plateau_score(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/deload_recommendation")
        def stats_deload_recommendation(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.deload_recommendation(
                exercise,
                start_date,
                end_date,
            )

        @self.app.get("/stats/performance_momentum")
        def stats_performance_momentum(
            exercise: str,
            start_date: str = None,
            end_date: str = None,
        ):
            return self.statistics.performance_momentum(
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
                {"id": tid, "date": date, "weights": weights}
                for tid, date, weights in tests
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

        @self.app.post("/body_weight")
        def log_body_weight(weight: float, date: str = None):
            try:
                log_date = (
                    datetime.date.today()
                    if date is None
                    else datetime.date.fromisoformat(date)
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid date format")
            wid = self.body_weights.log(log_date.isoformat(), weight)
            return {"id": wid}

        @self.app.get("/body_weight")
        def list_body_weight(start_date: str = None, end_date: str = None):
            rows = self.body_weights.fetch_history(start_date, end_date)
            return [{"id": rid, "date": d, "weight": w} for rid, d, w in rows]

        @self.app.put("/body_weight/{entry_id}")
        def update_body_weight(entry_id: int, weight: float, date: str):
            try:
                self.body_weights.update(entry_id, date, weight)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/body_weight/{entry_id}")
        def delete_body_weight(entry_id: int):
            try:
                self.body_weights.delete(entry_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.post("/wellness")
        def log_wellness(
            calories: float | None = None,
            sleep_hours: float | None = None,
            sleep_quality: float | None = None,
            stress_level: int | None = None,
            date: str | None = None,
        ):
            try:
                log_date = (
                    datetime.date.today()
                    if date is None
                    else datetime.date.fromisoformat(date)
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid date format")
            try:
                wid = self.wellness.log(
                    log_date.isoformat(),
                    calories,
                    sleep_hours,
                    sleep_quality,
                    stress_level,
                )
                return {"id": wid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/wellness")
        def list_wellness(start_date: str = None, end_date: str = None):
            rows = self.wellness.fetch_history(start_date, end_date)
            result = []
            for rid, d, cal, sh, sq, stress in rows:
                result.append(
                    {
                        "id": rid,
                        "date": d,
                        "calories": cal,
                        "sleep_hours": sh,
                        "sleep_quality": sq,
                        "stress_level": stress,
                    }
                )
            return result

        @self.app.put("/wellness/{entry_id}")
        def update_wellness(
            entry_id: int,
            date: str,
            calories: float | None = None,
            sleep_hours: float | None = None,
            sleep_quality: float | None = None,
            stress_level: int | None = None,
        ):
            try:
                self.wellness.update(
                    entry_id,
                    date,
                    calories,
                    sleep_hours,
                    sleep_quality,
                    stress_level,
                )
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/wellness/{entry_id}")
        def delete_wellness(entry_id: int):
            try:
                self.wellness.delete(entry_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.post("/workouts/{workout_id}/heart_rate")
        def log_heart_rate(workout_id: int, timestamp: str, heart_rate: int):
            try:
                hid = self.heart_rates.log(workout_id, timestamp, heart_rate)
                return {"id": hid}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/workouts/{workout_id}/heart_rate")
        def list_workout_heart_rate(workout_id: int):
            rows = self.heart_rates.fetch_for_workout(workout_id)
            return [
                {"id": rid, "timestamp": ts, "heart_rate": hr} for rid, ts, hr in rows
            ]

        @self.app.get("/heart_rate")
        def list_heart_rate(start_date: str = None, end_date: str = None):
            rows = self.heart_rates.fetch_range(start_date, end_date)
            return [
                {
                    "id": rid,
                    "workout_id": wid,
                    "timestamp": ts,
                    "heart_rate": hr,
                }
                for rid, wid, ts, hr in rows
            ]

        @self.app.put("/heart_rate/{entry_id}")
        def update_heart_rate(entry_id: int, timestamp: str, heart_rate: int):
            try:
                self.heart_rates.update(entry_id, timestamp, heart_rate)
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.delete("/heart_rate/{entry_id}")
        def delete_heart_rate(entry_id: int):
            try:
                self.heart_rates.delete(entry_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.get("/goals")
        def list_goals():
            rows = self.goals.fetch_all()
            return [
                {
                    "id": gid,
                    "exercise_name": ex,
                    "name": name,
                    "target_value": val,
                    "unit": unit,
                    "start_date": start,
                    "target_date": target,
                    "achieved": bool(ach),
                }
                for gid, ex, name, val, unit, start, target, ach in rows
            ]

        @self.app.post("/goals")
        def add_goal(
            exercise_name: str,
            name: str,
            target_value: float,
            unit: str,
            start_date: str,
            target_date: str,
        ):
            if not exercise_name:
                raise HTTPException(status_code=400, detail="exercise required")
            gid = self.goals.add(
                exercise_name, name, target_value, unit, start_date, target_date
            )
            return {"id": gid}

        @self.app.put("/goals/{goal_id}")
        def update_goal(
            goal_id: int,
            exercise_name: str | None = None,
            name: str | None = None,
            target_value: float | None = None,
            unit: str | None = None,
            start_date: str | None = None,
            target_date: str | None = None,
            achieved: bool | None = None,
        ):
            try:
                self.goals.update(
                    goal_id,
                    exercise_name,
                    name,
                    target_value,
                    unit,
                    start_date,
                    target_date,
                    achieved,
                )
                return {"status": "updated"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.delete("/goals/{goal_id}")
        def delete_goal(goal_id: int):
            try:
                self.goals.delete(goal_id)
                return {"status": "deleted"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.get("/stats/weight_stats")
        def stats_weight_stats(start_date: str = None, end_date: str = None):
            return self.statistics.weight_stats(start_date, end_date)

        @self.app.get("/stats/readiness_stats")
        def stats_readiness_stats(start_date: str = None, end_date: str = None):
            return self.statistics.readiness_stats(start_date, end_date)

        @self.app.get("/stats/weight_forecast")
        def stats_weight_forecast(days: int):
            return self.statistics.weight_forecast(days)

        @self.app.get("/stats/wellness_summary")
        def stats_wellness_summary(start_date: str = None, end_date: str = None):
            return self.statistics.wellness_summary(start_date, end_date)

        @self.app.get("/stats/bmi")
        def stats_bmi():
            return {"bmi": self.statistics.bmi()}

        @self.app.get("/stats/bmi_history")
        def stats_bmi_history(start_date: str = None, end_date: str = None):
            return self.statistics.bmi_history(start_date, end_date)

        @self.app.get("/stats/rating_history")
        def stats_rating_history(start_date: str = None, end_date: str = None):
            return self.statistics.rating_history(start_date, end_date)

        @self.app.get("/stats/rating_stats")
        def stats_rating_stats(start_date: str = None, end_date: str = None):
            return self.statistics.rating_stats(start_date, end_date)

        @self.app.get("/stats/heart_rate_summary")
        def stats_heart_rate_summary(start_date: str = None, end_date: str = None):
            return self.statistics.heart_rate_summary(start_date, end_date)

        @self.app.get("/stats/heart_rate_zones")
        def stats_heart_rate_zones(start_date: str = None, end_date: str = None):
            return self.statistics.heart_rate_zones(start_date, end_date)

        @self.app.get("/ml_logs/{model_name}")
        def get_ml_logs(model_name: str, start_date: str = None, end_date: str = None):
            rows = self.ml_logs.fetch_range(model_name, start_date, end_date)
            return [
                {
                    "timestamp": ts,
                    "prediction": pred,
                    "confidence": conf,
                }
                for ts, pred, conf in rows
            ]

        @self.app.get("/autoplanner/status")
        def autoplan_status():
            last_success = self.autoplan_logs.last_success()
            errors = [
                {"timestamp": ts, "message": msg}
                for ts, msg in self.autoplan_logs.last_errors(5)
            ]
            presc_success = self.prescription_logs.last_success()
            presc_errors = [
                {"timestamp": ts, "message": msg}
                for ts, msg in self.prescription_logs.last_errors(5)
            ]
            model_map = {
                "performance_model": "rpe",
                "volume_model": "volume",
                "readiness_model": "readiness",
                "progress_model": "progress",
                "rl_goal_model": "goal",
                "injury_model": "injury",
                "adaptation_model": "adaptation",
            }
            models = []
            for name, prefix in model_map.items():
                train_flag = self.settings.get_bool(
                    f"ml_{prefix}_training_enabled", True
                )
                pred_flag = self.settings.get_bool(
                    f"ml_{prefix}_prediction_enabled", True
                )
                if not train_flag and not pred_flag:
                    continue
                status = self.ml_status.fetch(name)
                models.append(
                    {
                        "name": name,
                        "training_enabled": train_flag,
                        "prediction_enabled": pred_flag,
                        "last_loaded": status["last_loaded"],
                        "last_train": status["last_train"],
                        "last_predict": status["last_predict"],
                    }
                )
            return {
                "last_success": last_success,
                "errors": errors,
                "models": models,
                "prescription_last_success": presc_success,
                "prescription_errors": presc_errors,
            }

        @self.app.get("/settings/general")
        def get_general_settings():
            return self.settings.all_settings()

        @self.app.post("/settings/general")
        def update_general_settings(
            body_weight: float = None,
            height: float = None,
            months_active: float = None,
            theme: str = None,
            color_theme: str = None,
            ml_all_enabled: bool = None,
            ml_training_enabled: bool = None,
            ml_prediction_enabled: bool = None,
            ml_rpe_training_enabled: bool = None,
            ml_rpe_prediction_enabled: bool = None,
            ml_volume_training_enabled: bool = None,
            ml_volume_prediction_enabled: bool = None,
            ml_readiness_training_enabled: bool = None,
            ml_readiness_prediction_enabled: bool = None,
            ml_progress_training_enabled: bool = None,
            ml_progress_prediction_enabled: bool = None,
            ml_goal_training_enabled: bool = None,
            ml_goal_prediction_enabled: bool = None,
            ml_injury_training_enabled: bool = None,
            ml_injury_prediction_enabled: bool = None,
            hide_preconfigured_equipment: bool = None,
            hide_preconfigured_exercises: bool = None,
            compact_mode: bool = None,
        ):
            if body_weight is not None:
                self.settings.set_float("body_weight", body_weight)
            if height is not None:
                self.settings.set_float("height", height)
            if months_active is not None:
                self.settings.set_float("months_active", months_active)
            if theme is not None:
                self.settings.set_text("theme", theme)
            if color_theme is not None:
                self.settings.set_text("color_theme", color_theme)
            if ml_all_enabled is not None:
                self.settings.set_bool("ml_all_enabled", ml_all_enabled)
            if ml_training_enabled is not None:
                self.settings.set_bool("ml_training_enabled", ml_training_enabled)
            if ml_prediction_enabled is not None:
                self.settings.set_bool("ml_prediction_enabled", ml_prediction_enabled)
            if ml_rpe_training_enabled is not None:
                self.settings.set_bool(
                    "ml_rpe_training_enabled", ml_rpe_training_enabled
                )
            if ml_rpe_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_rpe_prediction_enabled", ml_rpe_prediction_enabled
                )
            if ml_volume_training_enabled is not None:
                self.settings.set_bool(
                    "ml_volume_training_enabled", ml_volume_training_enabled
                )
            if ml_volume_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_volume_prediction_enabled", ml_volume_prediction_enabled
                )
            if ml_readiness_training_enabled is not None:
                self.settings.set_bool(
                    "ml_readiness_training_enabled", ml_readiness_training_enabled
                )
            if ml_readiness_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_readiness_prediction_enabled", ml_readiness_prediction_enabled
                )
            if ml_progress_training_enabled is not None:
                self.settings.set_bool(
                    "ml_progress_training_enabled", ml_progress_training_enabled
                )
            if ml_progress_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_progress_prediction_enabled", ml_progress_prediction_enabled
                )
            if ml_goal_training_enabled is not None:
                self.settings.set_bool(
                    "ml_goal_training_enabled", ml_goal_training_enabled
                )
            if ml_goal_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_goal_prediction_enabled", ml_goal_prediction_enabled
                )
            if ml_injury_training_enabled is not None:
                self.settings.set_bool(
                    "ml_injury_training_enabled", ml_injury_training_enabled
                )
            if ml_injury_prediction_enabled is not None:
                self.settings.set_bool(
                    "ml_injury_prediction_enabled", ml_injury_prediction_enabled
                )
            if hide_preconfigured_equipment is not None:
                self.settings.set_bool(
                    "hide_preconfigured_equipment", hide_preconfigured_equipment
                )
            if hide_preconfigured_exercises is not None:
                self.settings.set_bool(
                    "hide_preconfigured_exercises", hide_preconfigured_exercises
                )
            if compact_mode is not None:
                self.settings.set_bool("compact_mode", compact_mode)
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

        @self.app.post("/settings/git_pull")
        def git_pull():
            try:
                output = GitTools.git_pull("~/thebuilder")
                return {"status": "pulled", "output": output}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))


api = GymAPI()
app = api.app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
