import datetime
from typing import Optional
import streamlit as st
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
    ExerciseCatalogRepository,
    MuscleRepository,
    ExerciseNameRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
    GamificationRepository,
    MLModelRepository,
    MLLogRepository,
    BodyWeightRepository,
    WellnessRepository,
    FavoriteExerciseRepository,
    FavoriteTemplateRepository,
    FavoriteWorkoutRepository,
    TagRepository,
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
)
from tools import MathTools


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(self, yaml_path: str = "settings.yaml") -> None:
        self.settings_repo = SettingsRepository(yaml_path=yaml_path)
        self.theme = self.settings_repo.get_text("theme", "light")
        self._configure_page()
        self._inject_responsive_css()
        self._apply_theme()
        self.workouts = WorkoutRepository()
        self.exercises = ExerciseRepository()
        self.sets = SetRepository()
        self.planned_workouts = PlannedWorkoutRepository()
        self.planned_exercises = PlannedExerciseRepository()
        self.planned_sets = PlannedSetRepository()
        self.template_workouts = TemplateWorkoutRepository()
        self.template_exercises = TemplateExerciseRepository()
        self.template_sets = TemplateSetRepository()
        self.equipment = EquipmentRepository()
        self.exercise_catalog = ExerciseCatalogRepository()
        self.muscles_repo = MuscleRepository()
        self.exercise_names_repo = ExerciseNameRepository()
        self.favorites_repo = FavoriteExerciseRepository()
        self.favorite_templates_repo = FavoriteTemplateRepository()
        self.favorite_workouts_repo = FavoriteWorkoutRepository()
        self.tags_repo = TagRepository()
        self.pyramid_tests = PyramidTestRepository()
        self.pyramid_entries = PyramidEntryRepository()
        self.game_repo = GamificationRepository()
        self.ml_models = MLModelRepository()
        self.ml_logs = MLLogRepository()
        self.body_weights_repo = BodyWeightRepository()
        self.wellness_repo = WellnessRepository()
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings_repo,
        )
        self.ml_service = PerformanceModelService(
            self.ml_models,
            self.exercise_names_repo,
            self.ml_logs,
        )
        self.volume_model = VolumeModelService(self.ml_models)
        self.readiness_model = ReadinessModelService(self.ml_models)
        self.progress_model = ProgressModelService(self.ml_models)
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
        )
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
            self.gamification,
            self.ml_service,
            body_weight_repo=self.body_weights_repo,
        )
        self.stats = StatisticsService(
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
            self.volume_model,
            self.readiness_model,
            self.progress_model,
            None,
            None,
            self.body_weights_repo,
            self.equipment,
            self.wellness_repo,
        )
        self._state_init()

    def _refresh(self) -> None:
        """Reload the application state."""
        if st.button("Refresh"):
            st.experimental_rerun()

    def _configure_page(self) -> None:
        if st.session_state.get("layout_set"):
            return
        params = st.experimental_get_query_params()
        mode = params.get("mode", [None])[0]
        if mode is None:
            st.components.v1.html(
                """
                <script>
                const mode = window.innerWidth < 768 ? 'mobile' : 'desktop';
                const params = new URLSearchParams(window.location.search);
                params.set('mode', mode);
                window.location.search = params.toString();
                </script>
                """,
                height=0,
            )
            st.stop()
        layout = "centered" if mode == "mobile" else "wide"
        st.set_page_config(page_title="Workout Logger", layout=layout)
        st.markdown(
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            unsafe_allow_html=True,
        )
        st.session_state.layout_set = True
        st.session_state.is_mobile = mode == "mobile"
        st.components.v1.html(
            """
            <script>
            function setMode() {
                const mode = window.innerWidth < 768 ? 'mobile' : 'desktop';
                const params = new URLSearchParams(window.location.search);
                const cur = params.get('mode');
                if (mode !== cur) {
                    params.set('mode', mode);
                    window.location.search = params.toString();
                }
            }
            window.addEventListener('resize', setMode);
            window.addEventListener('orientationchange', setMode);
            </script>
            """,
            height=0,
        )

    def _inject_responsive_css(self) -> None:
        st.markdown(
            """
            <style>
            @media screen and (max-width: 768px) {
                div[data-testid="column"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                }
                button[kind="primary"],
                button[kind="secondary"] {
                    width: 100%;
                }
                div[data-testid="metric-container"] > label {
                    font-size: 0.9rem;
                }
                div[data-baseweb="input"] input,
                div[data-baseweb="select"] {
                    width: 100% !important;
                }
                div[data-testid="stTable"] table {
                    display: block;
                    overflow-x: auto;
                    white-space: nowrap;
                    width: 100%;
                }
                div[data-testid="metric-container"] > div {
                    flex-direction: column;
                    align-items: center;
                }
                body {
                    overflow-x: hidden;
                }
                canvas {
                    max-width: 100% !important;
                    height: auto !important;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _apply_theme(self) -> None:
        if self.theme == "dark":
            st.markdown(
                """
                <style>
                body {
                    background-color: #111;
                    color: #eee;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

    def _state_init(self) -> None:
        if "selected_workout" not in st.session_state:
            st.session_state.selected_workout = None
        if "exercise_inputs" not in st.session_state:
            st.session_state.exercise_inputs = {}
        if "selected_planned_workout" not in st.session_state:
            st.session_state.selected_planned_workout = None
        if "selected_template" not in st.session_state:
            st.session_state.selected_template = None
        if "pyramid_inputs" not in st.session_state:
            st.session_state.pyramid_inputs = [0.0]

    def _create_sidebar(self) -> None:
        st.sidebar.header("Quick Actions")
        if st.sidebar.button("New Workout"):
            wid = self.workouts.create(
                datetime.date.today().isoformat(),
                "strength",
                None,
                None,
            )
            st.session_state.selected_workout = wid
            st.sidebar.success(f"Created workout {wid}")
        with st.sidebar.expander("Help & About"):
            if st.button("Show Help", key="help_btn"):
                self._help_dialog()
            if st.button("Show About", key="about_btn"):
                self._about_dialog()

    def _help_dialog(self) -> None:
        with st.dialog("Help"):
            st.markdown("## Workout Logger Help")
            st.markdown(
                "Use the tabs to log workouts, plan sessions, and analyze your training data."
            )
            st.markdown(
                "All data is saved to an internal database and can be managed via the settings tab."
            )
            st.button("Close")

    def _about_dialog(self) -> None:
        with st.dialog("About"):
            st.markdown("## About The Builder")
            st.markdown(
                "This application is a comprehensive workout planner and logger built with Streamlit and FastAPI."
            )
            st.markdown(
                "It offers a responsive interface and a complete REST API for advanced tracking, planning and analytics."
            )
            st.button("Close")

    def _dashboard_tab(self) -> None:
        st.header("Dashboard")
        with st.expander("Filters", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="dash_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="dash_end")
        stats = self.stats.overview(start.isoformat(), end.isoformat())
        with st.expander("Overview Metrics", expanded=True):
            col_num = 2 if st.session_state.is_mobile else 4
            cols = st.columns(col_num)
            metrics = [
                ("Workouts", stats["workouts"]),
                ("Volume", stats["volume"]),
                ("Avg RPE", stats["avg_rpe"]),
                ("Exercises", stats["exercises"]),
                ("BMI", self.stats.bmi()),
            ]
            for idx, (label, val) in enumerate(metrics):
                cols[idx % col_num].metric(label, val)
        daily = self.stats.daily_volume(start.isoformat(), end.isoformat())
        with st.expander("Charts", expanded=True):
            st.subheader("Daily Volume")
            if daily:
                st.line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    x=[d["date"] for d in daily],
                )
            exercises = [""] + self.exercise_names_repo.fetch_all()
            ex_choice = st.selectbox("Exercise Progression", exercises, key="dash_ex")
            if ex_choice:
                prog = self.stats.progression(
                    ex_choice, start.isoformat(), end.isoformat()
                )
                st.subheader("1RM Progression")
                if prog:
                    st.line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        x=[p["date"] for p in prog],
                    )
            records = self.stats.personal_records(
                ex_choice if ex_choice else None,
                start.isoformat(),
                end.isoformat(),
            )
            if records:
                with st.expander("Personal Records", expanded=False):
                    st.table(records[:5])
            eq_stats = self.stats.equipment_usage(start.isoformat(), end.isoformat())
            if eq_stats:
                st.subheader("Equipment Usage")
                st.bar_chart(
                    {"Sets": [e["sets"] for e in eq_stats]},
                    x=[e["equipment"] for e in eq_stats],
                )
            top_ex = self.stats.exercise_summary(
                None, start.isoformat(), end.isoformat()
            )
            top_ex.sort(key=lambda x: x["volume"], reverse=True)
            if top_ex:
                with st.expander("Top Exercises", expanded=False):
                    st.table(top_ex[:5])

    def run(self) -> None:
        st.title("Workout Logger")
        self._create_sidebar()
        self._refresh()
        (
            workouts_tab,
            library_tab,
            progress_tab,
            settings_tab,
        ) = st.tabs(
            [
                "Workouts",
                "Library",
                "Progress",
                "Settings",
            ]
        )
        with workouts_tab:
            log_sub, plan_sub = st.tabs(["Log", "Plan"])
            with log_sub:
                self._log_tab()
            with plan_sub:
                self._plan_tab()
        with library_tab:
            self._library_tab()
        with progress_tab:
            (
                history_sub,
                dash_sub,
                stats_sub,
                insights_sub,
                weight_sub,
                rep_sub,
                game_sub,
                tests_sub,
            ) = st.tabs(
                [
                    "History",
                    "Dashboard",
                    "Exercise Stats",
                    "Insights",
                    "Body Weight",
                    "Reports",
                    "Gamification",
                    "Tests",
                ]
            )
            with history_sub:
                self._history_tab()
            with dash_sub:
                self._dashboard_tab()
            with stats_sub:
                self._stats_tab()
            with insights_sub:
                self._insights_tab()
            with weight_sub:
                self._weight_tab()
            with rep_sub:
                self._reports_tab()
            with game_sub:
                self._gamification_tab()
            with tests_sub:
                self._tests_tab()
        with settings_tab:
            self._settings_tab()

    def _log_tab(self) -> None:
        plans = self.planned_workouts.fetch_all()
        options = {str(p[0]): p for p in plans}
        if options:
            with st.expander("Use Planned Workout", expanded=False):
                selected = st.selectbox(
                    "Planned Workout",
                    [""] + list(options.keys()),
                    format_func=lambda x: "None" if x == "" else options[x][1],
                    key="log_plan_select",
                )
                if selected and st.button("Use Plan"):
                    new_id = self.planner.create_workout_from_plan(int(selected))
                    st.session_state.selected_workout = new_id
        self._workout_section()
        if st.session_state.selected_workout:
            self._exercise_section()

    def _plan_tab(self) -> None:
        self._template_section()
        if st.session_state.get("selected_template") is not None:
            self._template_exercise_section()
        self._planned_workout_section()
        if st.session_state.selected_planned_workout:
            self._planned_exercise_section()

    def _workout_section(self) -> None:
        st.header("Workouts")
        training_options = ["strength", "hypertrophy", "highintensity"]
        with st.expander("Workout Management", expanded=True):
            with st.expander("Create New Workout"):
                new_type = st.selectbox(
                    "Training Type", training_options, key="new_workout_type"
                )
                new_location = st.text_input("Location", key="new_workout_location")
                if st.button("New Workout"):
                    new_id = self.workouts.create(
                        datetime.date.today().isoformat(),
                        new_type,
                        None,
                        new_location or None,
                        None,
                    )
                    st.session_state.selected_workout = new_id
            with st.expander("Existing Workouts", expanded=True):
                workouts = self.workouts.fetch_all_workouts()
                options = {str(w[0]): w for w in workouts}
                if options:
                    selected = st.selectbox(
                        "Select Workout",
                        list(options.keys()),
                        format_func=lambda x: options[x][1],
                    )
                    st.session_state.selected_workout = int(selected)
                    detail = self.workouts.fetch_detail(int(selected))
                    start_time = detail[2]
                    end_time = detail[3]
                    current_type = detail[4]
                    notes_val = detail[5] or ""
                    loc_val = detail[6] or ""
                    rating_val = detail[7]
                    cols = st.columns(3)
                    if cols[0].button("Start Workout", key=f"start_workout_{selected}"):
                        self.workouts.set_start_time(
                            int(selected),
                            datetime.datetime.now().isoformat(timespec="seconds"),
                        )
                    if cols[1].button(
                        "Finish Workout", key=f"finish_workout_{selected}"
                    ):
                        self.workouts.set_end_time(
                            int(selected),
                            datetime.datetime.now().isoformat(timespec="seconds"),
                        )
                    type_choice = cols[2].selectbox(
                        "Type",
                        training_options,
                        index=training_options.index(current_type),
                        key=f"type_select_{selected}",
                    )
                    if cols[2].button("Save", key=f"save_type_{selected}"):
                        self.workouts.set_training_type(int(selected), type_choice)
                    if start_time:
                        st.write(f"Start: {start_time}")
                    if end_time:
                        st.write(f"End: {end_time}")
                    notes_edit = st.text_area(
                        "Notes",
                        value=notes_val,
                        key=f"workout_notes_{selected}",
                    )
                    if st.button("Save Notes", key=f"save_notes_{selected}"):
                        self.workouts.set_note(int(selected), notes_edit)
                    loc_edit = st.text_input(
                        "Location",
                        value=loc_val,
                        key=f"workout_location_{selected}",
                    )
                    if st.button("Save Location", key=f"save_location_{selected}"):
                        self.workouts.set_location(int(selected), loc_edit or None)
                    rating_edit = st.slider(
                        "Rating",
                        0,
                        5,
                        value=rating_val if rating_val is not None else 0,
                        key=f"rating_{selected}",
                    )
                    if st.button("Save Rating", key=f"save_rating_{selected}"):
                        self.workouts.set_rating(int(selected), int(rating_edit))
                    tags_all = self.tags_repo.fetch_all()
                    name_map = {n: tid for tid, n in tags_all}
                    current_tags = [
                        n for _, n in self.tags_repo.fetch_for_workout(int(selected))
                    ]
                    tag_sel = st.multiselect(
                        "Tags",
                        [n for _, n in tags_all],
                        current_tags,
                        key=f"tags_sel_{selected}",
                    )
                    if st.button("Save Tags", key=f"save_tags_{selected}"):
                        ids = [name_map[n] for n in tag_sel]
                        self.tags_repo.set_tags(int(selected), ids)
                    csv_data = self.sets.export_workout_csv(int(selected))
                    st.download_button(
                        label="Export CSV",
                        data=csv_data,
                        file_name=f"workout_{selected}.csv",
                        mime="text/csv",
                        key=f"export_{selected}",
                    )

    def _exercise_section(self) -> None:
        st.header("Exercises")
        workout_id = st.session_state.selected_workout
        with st.expander("Exercise Management", expanded=True):
            with st.expander("Add New Exercise"):
                ex_name = self._exercise_selector(
                    "log_new",
                    None,
                    st.session_state.get("log_new_groups", []),
                    st.session_state.get("log_new_muscles", []),
                )
                eq = self._equipment_selector(
                    "log_new",
                    st.session_state.get("log_new_muscles", []),
                )
                note_val = st.text_input("Note", key="new_exercise_note")
                if st.button("Add Exercise"):
                    if ex_name and eq:
                        self.exercises.add(workout_id, ex_name, eq, note_val or None)
                    else:
                        st.warning("Exercise and equipment required")
            with st.expander("Logged Exercises", expanded=True):
                exercises = self.exercises.fetch_for_workout(workout_id)
                for ex_id, name, eq_name, note in exercises:
                    self._exercise_card(ex_id, name, eq_name, note)
            summary = self.sets.workout_summary(workout_id)
            with st.expander("Workout Summary", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Volume", summary["volume"])
                col2.metric("Sets", summary["sets"])
                col3.metric("Avg RPE", summary["avg_rpe"])

    def _exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str], note: Optional[str]
    ) -> None:
        sets = self.sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
        if note:
            header += f" - {note}"
        expander = st.expander(header)
        with expander:
            if st.button("Remove Exercise", key=f"remove_ex_{exercise_id}"):
                self.exercises.remove(exercise_id)
                return
            if equipment:
                muscles = self.equipment.fetch_muscles(equipment)
                st.markdown("**Muscles:**")
                for m in muscles:
                    st.markdown(f"- {m}")
            note_val = st.text_input(
                "Note", value=note or "", key=f"note_{exercise_id}"
            )
            if st.button("Update Note", key=f"upd_note_{exercise_id}"):
                self.exercises.update_note(exercise_id, note_val or None)
            with st.expander("Sets", expanded=True):
                for set_id, reps, weight, rpe, start_time, end_time in sets:
                    detail = self.sets.fetch_detail(set_id)
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {set_id}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"reps_{set_id}",
                            )
                            weight_val = st.number_input(
                                "Weight (kg)",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"weight_{set_id}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"rpe_{set_id}",
                            )
                            note_val = st.text_input(
                                "Note",
                                value=detail.get("note") or "",
                                key=f"note_{set_id}",
                            )
                            st.write(f"{detail['diff_reps']:+}")
                            st.write(f"{detail['diff_weight']:+.1f}")
                            st.write(f"{detail['diff_rpe']:+}")
                            start_col, finish_col = st.columns(2)
                            if start_col.button("Start", key=f"start_set_{set_id}"):
                                self.sets.set_start_time(
                                    set_id,
                                    datetime.datetime.now().isoformat(timespec="seconds"),
                                )
                            if finish_col.button("Finish", key=f"finish_set_{set_id}"):
                                self.sets.set_end_time(
                                    set_id,
                                    datetime.datetime.now().isoformat(timespec="seconds"),
                                )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"del_{set_id}"):
                                self._confirm_delete_set(set_id)
                                continue
                            if upd_col.button("Update", key=f"upd_{set_id}"):
                                self.sets.update(
                                    set_id, int(reps_val), float(weight_val), int(rpe_val)
                                )
                                self.sets.update_note(set_id, note_val or None)
                            if start_time:
                                st.write(start_time)
                            if end_time:
                                st.write(end_time)
                    else:
                        cols = st.columns(12)
                        with cols[0]:
                            st.write(f"Set {set_id}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"reps_{set_id}",
                        )
                        weight_val = cols[2].number_input(
                            "Weight (kg)",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"weight_{set_id}",
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"rpe_{set_id}",
                        )
                        note_val = cols[4].text_input(
                            "Note",
                            value=detail.get("note") or "",
                            key=f"note_{set_id}",
                        )
                        cols[5].write(f"{detail['diff_reps']:+}")
                        cols[6].write(f"{detail['diff_weight']:+.1f}")
                        cols[7].write(f"{detail['diff_rpe']:+}")
                        if cols[8].button("Start", key=f"start_set_{set_id}"):
                            self.sets.set_start_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                        if cols[9].button("Finish", key=f"finish_set_{set_id}"):
                            self.sets.set_end_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                        if cols[10].button("Delete", key=f"del_{set_id}"):
                            self._confirm_delete_set(set_id)
                            continue
                        if cols[11].button("Update", key=f"upd_{set_id}"):
                            self.sets.update(
                                set_id, int(reps_val), float(weight_val), int(rpe_val)
                            )
                            self.sets.update_note(set_id, note_val or None)
                        if start_time:
                            cols[8].write(start_time)
                        if end_time:
                            cols[9].write(end_time)
            hist = self.stats.exercise_history(name)
            if hist:
                with st.expander("History (last 5)"):
                    st.table(hist[-5:][::-1])
                with st.expander("Weight Progress"):
                    st.line_chart(
                        {"Weight": [h["weight"] for h in hist]},
                        x=[h["date"] for h in hist],
                    )
                prog = self.stats.progression(name)
                if prog:
                    with st.expander("1RM Progress"):
                        st.line_chart(
                            {"Est 1RM": [p["est_1rm"] for p in prog]},
                            x=[p["date"] for p in prog],
                        )
            if self.recommender.has_history(name):
                if st.button("Recommend Next Set", key=f"rec_next_{exercise_id}"):
                    try:
                        self.recommender.recommend_next_set(exercise_id)
                    except ValueError as e:
                        st.warning(str(e))
            with st.expander("Add Set"):
                self._add_set_form(exercise_id)
            if st.button("Bulk Add Sets", key=f"bulk_{exercise_id}"):
                self._bulk_add_sets_dialog(exercise_id)

    def _add_set_form(self, exercise_id: int) -> None:
        reps = st.number_input(
            "Reps",
            min_value=1,
            step=1,
            key=f"new_reps_{exercise_id}",
        )
        weight = st.number_input(
            "Weight (kg)",
            min_value=0.0,
            step=0.5,
            key=f"new_weight_{exercise_id}",
        )
        rpe = st.selectbox(
            "RPE",
            options=list(range(11)),
            key=f"new_rpe_{exercise_id}",
        )
        note = st.text_input("Note", key=f"new_note_{exercise_id}")
        last = self.sets.fetch_for_exercise(exercise_id)
        if last:
            if st.button("Copy Last Set", key=f"copy_{exercise_id}"):
                l = last[-1]
                st.session_state[f"new_reps_{exercise_id}"] = int(l[1])
                st.session_state[f"new_weight_{exercise_id}"] = float(l[2])
                st.session_state[f"new_rpe_{exercise_id}"] = int(l[3])
        if st.button("Add Set", key=f"add_set_{exercise_id}"):
            self.sets.add(exercise_id, int(reps), float(weight), int(rpe), note or None)
            self.gamification.record_set(
                exercise_id, int(reps), float(weight), int(rpe)
            )
            st.session_state.pop(f"new_reps_{exercise_id}", None)
            st.session_state.pop(f"new_weight_{exercise_id}", None)
            st.session_state.pop(f"new_rpe_{exercise_id}", None)

    def _bulk_add_sets_dialog(self, exercise_id: int) -> None:
        with st.dialog("Bulk Add Sets"):
            st.markdown("Enter one set per line as `reps,weight,rpe`")
            text = st.text_area("Sets", key=f"bulk_text_{exercise_id}")
            if st.button("Add", key=f"bulk_add_{exercise_id}"):
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                added = 0
                for line in lines:
                    try:
                        r_s, w_s, rpe_s = [p.strip() for p in line.split(",")]
                        reps_i = int(r_s)
                        weight_f = float(w_s)
                        rpe_i = int(rpe_s)
                    except Exception:
                        st.warning(f"Invalid line: {line}")
                        continue
                    self.sets.add(exercise_id, reps_i, weight_f, rpe_i)
                    self.gamification.record_set(exercise_id, reps_i, weight_f, rpe_i)
                    added += 1
                if added:
                    st.success(f"Added {added} sets")
                st.session_state.pop(f"bulk_text_{exercise_id}", None)
            st.button("Close", key=f"bulk_close_{exercise_id}")

    def _confirm_delete_set(self, set_id: int) -> None:
        with st.dialog("Confirm Delete"):
            st.write(f"Delete set {set_id}?")
            cols = st.columns(2)
            if cols[0].button("Yes", key=f"yes_{set_id}"):
                self.sets.remove(set_id)
                st.experimental_rerun()
            if cols[1].button("No", key=f"no_{set_id}"):
                st.experimental_rerun()

    def _equipment_selector(
        self, prefix: str, muscles: Optional[list] = None
    ) -> Optional[str]:
        types = [""] + self.equipment.fetch_types()
        eq_type = st.selectbox("Equipment Type", types, key=f"{prefix}_type")
        filter_text = st.text_input("Filter Equipment", key=f"{prefix}_filter")
        names = self.equipment.fetch_names(
            eq_type if eq_type else None,
            filter_text or None,
            muscles,
        )
        eq_name = st.selectbox("Equipment Name", [""] + names, key=f"{prefix}_name")
        if eq_name:
            muscles = self.equipment.fetch_muscles(eq_name)
            st.markdown("Muscles Trained:")
            for m in muscles:
                st.markdown(f"- {m}")
        return eq_name or None

    def _exercise_selector(
        self,
        prefix: str,
        equipment: Optional[str],
        selected_groups: list,
        selected_muscles: list,
    ) -> Optional[str]:
        groups = self.exercise_catalog.fetch_muscle_groups()
        all_muscles = self.muscles_repo.fetch_all()
        group_sel = st.multiselect(
            "Muscle Groups",
            groups,
            default=selected_groups,
            key=f"{prefix}_groups",
        )
        muscle_sel = st.multiselect(
            "Filter Muscles",
            all_muscles,
            default=selected_muscles,
            key=f"{prefix}_muscles",
        )
        name_filter = st.text_input(
            "Name Contains",
            key=f"{prefix}_name_filter",
        )
        names = self.exercise_catalog.fetch_names(
            group_sel or None,
            muscle_sel or None,
            equipment,
            name_filter or None,
        )
        ex_name = st.selectbox("Exercise", [""] + names, key=f"{prefix}_exercise")
        if ex_name:
            detail = self.exercise_catalog.fetch_detail(ex_name)
            if detail:
                (
                    group,
                    variants,
                    eq_names,
                    primary,
                    secondary,
                    tertiary,
                    other,
                    _,
                ) = detail
                st.markdown(f"**Primary:** {primary}")
                if secondary:
                    st.markdown("**Secondary:**")
                    for m in secondary.split("|"):
                        st.markdown(f"- {m}")
                if tertiary:
                    st.markdown("**Tertiary:**")
                    for m in tertiary.split("|"):
                        st.markdown(f"- {m}")
                if other:
                    st.markdown("**Other:**")
                    for m in other.split("|"):
                        st.markdown(f"- {m}")
                if variants:
                    st.markdown("**Variants:**")
                    for v in variants.split("|"):
                        st.markdown(f"- {v}")
        return ex_name or None

    def _planned_workout_section(self) -> None:
        st.header("Planned Workouts")
        with st.expander("Plan Management", expanded=True):
            with st.expander("Create New Plan"):
                plan_date = st.date_input(
                    "Plan Date", datetime.date.today(), key="plan_date"
                )
                training_options = ["strength", "hypertrophy", "highintensity"]
                plan_type = st.selectbox(
                    "Training Type",
                    training_options,
                    key="plan_type",
                )
                if st.button("New Planned Workout"):
                    pid = self.planned_workouts.create(plan_date.isoformat(), plan_type)
                    st.session_state.selected_planned_workout = pid
            with st.expander("Existing Plans", expanded=True):
                plans = self.planned_workouts.fetch_all()
                options = {str(p[0]): p for p in plans}
                if options:
                    selected = st.selectbox(
                        "Select Planned Workout",
                        list(options.keys()),
                        format_func=lambda x: options[x][1],
                        key="select_planned_workout",
                    )
                    st.session_state.selected_planned_workout = int(selected)
                    for pid, pdate, ptype in plans:
                        with st.expander(f"{pdate} (ID {pid})", expanded=False):
                            edit_date = st.date_input(
                                "New Date",
                                datetime.date.fromisoformat(pdate),
                                key=f"plan_edit_{pid}",
                            )
                            type_choice = st.selectbox(
                                "Type",
                                training_options,
                                index=training_options.index(ptype),
                                key=f"plan_type_{pid}",
                            )
                            dup_date = st.date_input(
                                "Duplicate To",
                                datetime.date.fromisoformat(pdate),
                                key=f"plan_dup_{pid}",
                            )
                            cols = st.columns(3)
                            if cols[0].button("Save", key=f"save_plan_{pid}"):
                                self.planned_workouts.update_date(
                                    pid, edit_date.isoformat()
                                )
                                self.planned_workouts.set_training_type(
                                    pid, type_choice
                                )
                                st.success("Updated")
                            if cols[1].button("Duplicate", key=f"dup_plan_{pid}"):
                                self.planner.duplicate_plan(pid, dup_date.isoformat())
                                st.success("Duplicated")
                            if cols[2].button("Delete", key=f"del_plan_{pid}"):
                                self.planned_workouts.delete(pid)
                                st.success("Deleted")

    def _planned_exercise_section(self) -> None:
        st.header("Planned Exercises")
        workout_id = st.session_state.selected_planned_workout
        with st.expander("Planned Exercise Management", expanded=True):
            with st.expander("Add Planned Exercise"):
                ex_name = self._exercise_selector(
                    "plan_new",
                    None,
                    st.session_state.get("plan_new_groups", []),
                    st.session_state.get("plan_new_muscles", []),
                )
                plan_eq = self._equipment_selector(
                    "plan_new",
                    st.session_state.get("plan_new_muscles", []),
                )
                if st.button("Add Planned Exercise"):
                    if ex_name and plan_eq:
                        self.planned_exercises.add(workout_id, ex_name, plan_eq)
                    else:
                        st.warning("Exercise and equipment required")
            with st.expander("Planned Exercise List", expanded=True):
                exercises = self.planned_exercises.fetch_for_workout(workout_id)
                for ex_id, name, eq_name in exercises:
                    self._planned_exercise_card(ex_id, name, eq_name)

    def _planned_exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str]
    ) -> None:
        sets = self.planned_sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
        expander = st.expander(header)
        with expander:
            if st.button("Remove Planned Exercise", key=f"rem_plan_ex_{exercise_id}"):
                self.planned_exercises.remove(exercise_id)
                return
            if equipment:
                muscles = self.equipment.fetch_muscles(equipment)
                st.markdown("**Muscles:**")
                for m in muscles:
                    st.markdown(f"- {m}")
            with st.expander("Sets", expanded=True):
                for set_id, reps, weight, rpe in sets:
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {set_id}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"plan_reps_{set_id}",
                            )
                            weight_val = st.number_input(
                                "Weight (kg)",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"plan_weight_{set_id}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"plan_rpe_{set_id}",
                            )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"del_plan_set_{set_id}"):
                                self.planned_sets.remove(set_id)
                                continue
                            if upd_col.button("Update", key=f"upd_plan_set_{set_id}"):
                                self.planned_sets.update(
                                    set_id, int(reps_val), float(weight_val), int(rpe_val)
                                )
                    else:
                        cols = st.columns(6)
                        cols[0].write(f"Set {set_id}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"plan_reps_{set_id}",
                        )
                        weight_val = cols[2].number_input(
                            "Weight (kg)",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"plan_weight_{set_id}",
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"plan_rpe_{set_id}",
                        )
                        if cols[4].button("Delete", key=f"del_plan_set_{set_id}"):
                            self.planned_sets.remove(set_id)
                            continue
                        if cols[5].button("Update", key=f"upd_plan_set_{set_id}"):
                            self.planned_sets.update(
                                set_id, int(reps_val), float(weight_val), int(rpe_val)
                            )
            with st.expander("Add Planned Set"):
                self._add_planned_set_form(exercise_id)

    def _add_planned_set_form(self, exercise_id: int) -> None:
        reps = st.number_input(
            "Reps",
            min_value=1,
            step=1,
            key=f"plan_new_reps_{exercise_id}",
        )
        weight = st.number_input(
            "Weight (kg)",
            min_value=0.0,
            step=0.5,
            key=f"plan_new_weight_{exercise_id}",
        )
        rpe = st.selectbox(
            "RPE",
            options=list(range(11)),
            key=f"plan_new_rpe_{exercise_id}",
        )
        if st.button("Add Planned Set", key=f"add_plan_set_{exercise_id}"):
            self.planned_sets.add(exercise_id, int(reps), float(weight), int(rpe))
            st.session_state.pop(f"plan_new_reps_{exercise_id}", None)
            st.session_state.pop(f"plan_new_weight_{exercise_id}", None)
            st.session_state.pop(f"plan_new_rpe_{exercise_id}", None)

    def _template_section(self) -> None:
        st.header("Templates")
        training_options = ["strength", "hypertrophy", "highintensity"]
        with st.expander("Template Management", expanded=True):
            favs = self.favorite_templates_repo.fetch_all()
            with st.expander("Favorite Templates", expanded=True):
                if favs:
                    for fid in favs:
                        try:
                            _id, name, _type = self.template_workouts.fetch_detail(fid)
                        except ValueError:
                            continue
                        cols = st.columns(2)
                        cols[0].write(name)
                        if cols[1].button("Remove", key=f"fav_tpl_rm_{fid}"):
                            self.favorite_templates_repo.remove(fid)
                            st.experimental_rerun()
                else:
                    st.write("No favorites.")
                templates = {
                    str(t[0]): t[1] for t in self.template_workouts.fetch_all()
                }
                add_choice = st.selectbox(
                    "Add Favorite",
                    [""] + list(templates.keys()),
                    format_func=lambda x: "" if x == "" else templates[x],
                    key="fav_tpl_add_choice",
                )
                if st.button("Add Favorite", key="fav_tpl_add_btn") and add_choice:
                    self.favorite_templates_repo.add(int(add_choice))
                    st.experimental_rerun()
            with st.expander("Create New Template"):
                name = st.text_input("Name", key="tmpl_name")
                t_type = st.selectbox(
                    "Training Type", training_options, key="tmpl_type"
                )
                if st.button("Create Template") and name:
                    tid = self.template_workouts.create(name, t_type)
                    st.session_state.selected_template = tid
            with st.expander("Existing Templates", expanded=True):
                templates = self.template_workouts.fetch_all()
                options = {str(t[0]): t for t in templates}
                if options:
                    selected = st.selectbox(
                        "Select Template",
                        list(options.keys()),
                        format_func=lambda x: options[x][1],
                        key="select_template",
                    )
                    st.session_state.selected_template = int(selected)
                    for tid, name, t_type in templates:
                        with st.expander(f"{name} (ID {tid})", expanded=False):
                            edit_name = st.text_input(
                                "Name", value=name, key=f"tmpl_edit_name_{tid}"
                            )
                            edit_type = st.selectbox(
                                "Type",
                                training_options,
                                index=training_options.index(t_type),
                                key=f"tmpl_edit_type_{tid}",
                            )
                            plan_date = st.date_input(
                                "Create Plan Date",
                                datetime.date.today(),
                                key=f"tmpl_plan_{tid}",
                            )
                            cols = st.columns(3)
                            if cols[0].button("Save", key=f"tmpl_save_{tid}"):
                                self.template_workouts.update(tid, edit_name, edit_type)
                                st.success("Updated")
                            if cols[1].button("Plan", key=f"tmpl_plan_btn_{tid}"):
                                self.planner.create_plan_from_template(
                                    tid, plan_date.isoformat()
                                )
                                st.success("Planned")
                            if cols[2].button("Delete", key=f"tmpl_del_{tid}"):
                                self.template_workouts.delete(tid)
                                st.success("Deleted")
                else:
                    st.write("No templates.")

    def _template_exercise_section(self) -> None:
        st.header("Template Exercises")
        template_id = st.session_state.selected_template
        with st.expander("Exercise Management", expanded=True):
            with st.expander("Add Exercise"):
                ex_name = self._exercise_selector(
                    "tmpl_new",
                    None,
                    st.session_state.get("tmpl_new_groups", []),
                    st.session_state.get("tmpl_new_muscles", []),
                )
                eq = self._equipment_selector(
                    "tmpl_new",
                    st.session_state.get("tmpl_new_muscles", []),
                )
                if st.button("Add Template Exercise"):
                    if ex_name and eq:
                        self.template_exercises.add(template_id, ex_name, eq)
                    else:
                        st.warning("Exercise and equipment required")
            with st.expander("Exercise List", expanded=True):
                exercises = self.template_exercises.fetch_for_template(template_id)
                for ex_id, name, eq in exercises:
                    self._template_exercise_card(ex_id, name, eq)

    def _template_exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str]
    ) -> None:
        sets = self.template_sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
        exp = st.expander(header)
        with exp:
            if st.button("Remove Exercise", key=f"tmpl_ex_rm_{exercise_id}"):
                self.template_exercises.remove(exercise_id)
                return
            with st.expander("Sets", expanded=True):
                for sid, reps, weight, rpe in sets:
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {sid}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"tmpl_reps_{sid}",
                            )
                            weight_val = st.number_input(
                                "Weight",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"tmpl_w_{sid}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"tmpl_rpe_{sid}",
                            )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"tmpl_del_set_{sid}"):
                                self.template_sets.remove(sid)
                                continue
                            if upd_col.button("Update", key=f"tmpl_upd_set_{sid}"):
                                self.template_sets.update(
                                    sid, int(reps_val), float(weight_val), int(rpe_val)
                                )
                    else:
                        cols = st.columns(5)
                        cols[0].write(f"Set {sid}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"tmpl_reps_{sid}",
                        )
                        weight_val = cols[2].number_input(
                            "Weight",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"tmpl_w_{sid}",
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"tmpl_rpe_{sid}",
                        )
                        if cols[4].button("Delete", key=f"tmpl_del_set_{sid}"):
                            self.template_sets.remove(sid)
                            continue
                        if cols[4].button("Update", key=f"tmpl_upd_set_{sid}"):
                            self.template_sets.update(
                                sid, int(reps_val), float(weight_val), int(rpe_val)
                            )
            with st.expander("Add Set"):
                reps = st.number_input(
                    "Reps", min_value=1, step=1, key=f"tmpl_new_reps_{exercise_id}"
                )
                weight = st.number_input(
                    "Weight", min_value=0.0, step=0.5, key=f"tmpl_new_w_{exercise_id}"
                )
                rpe = st.selectbox(
                    "RPE", options=list(range(11)), key=f"tmpl_new_rpe_{exercise_id}"
                )
                if st.button("Add Set", key=f"tmpl_add_set_{exercise_id}"):
                    self.template_sets.add(
                        exercise_id, int(reps), float(weight), int(rpe)
                    )
                    st.session_state.pop(f"tmpl_new_reps_{exercise_id}", None)
                    st.session_state.pop(f"tmpl_new_w_{exercise_id}", None)
                    st.session_state.pop(f"tmpl_new_rpe_{exercise_id}", None)

    def _library_tab(self) -> None:
        st.header("Library")
        eq_tab, ex_tab = st.tabs(["Equipment", "Exercises"])
        with eq_tab:
            self._equipment_library()
        with ex_tab:
            self._exercise_catalog_library()

    def _equipment_library(self) -> None:
        muscles = self.muscles_repo.fetch_all()
        types = [""] + self.equipment.fetch_types()
        with st.expander("Filters", expanded=True):
            sel_type = st.selectbox("Type", types, key="lib_eq_type")
            prefix = st.text_input("Name Contains", key="lib_eq_prefix")
            mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
        names = self.equipment.fetch_names(
            sel_type or None,
            prefix or None,
            mus_filter or None,
        )
        with st.expander("Equipment List", expanded=True):
            choice = st.selectbox("Equipment", [""] + names, key="lib_eq_name")
            if choice and st.button("Details", key="lib_eq_btn"):
                detail = self.equipment.fetch_detail(choice)
                if detail:
                    with st.dialog("Equipment Details"):
                        eq_type, muscs, _ = detail
                        st.markdown(f"**Type:** {eq_type}")
                        st.markdown("**Muscles:**")
                        for m in muscs:
                            st.markdown(f"- {m}")

    def _exercise_catalog_library(self) -> None:
        groups = self.exercise_catalog.fetch_muscle_groups()
        muscles = self.muscles_repo.fetch_all()
        favs = self.favorites_repo.fetch_all()
        with st.expander("Favorite Exercises", expanded=True):
            if favs:
                for f in favs:
                    cols = st.columns(2)
                    cols[0].write(f)
                    if cols[1].button("Remove", key=f"fav_rm_{f}"):
                        self.favorites_repo.remove(f)
                        st.experimental_rerun()
            else:
                st.write("No favorites.")
            add_choice = st.selectbox(
                "Add Favorite",
                [""] + self.exercise_names_repo.fetch_all(),
                key="fav_add_name",
            )
            if st.button("Add Favorite", key="fav_add_btn") and add_choice:
                self.favorites_repo.add(add_choice)
                st.experimental_rerun()
        with st.expander("Filters", expanded=True):
            sel_groups = st.multiselect("Muscle Groups", groups, key="lib_ex_groups")
            sel_mus = st.multiselect("Muscles", muscles, key="lib_ex_mus")
            eq_names = self.equipment.fetch_names()
            sel_eq = st.selectbox("Equipment", [""] + eq_names, key="lib_ex_eq")
            name_filter = st.text_input("Name Contains", key="lib_ex_prefix")
        names = self.exercise_catalog.fetch_names(
            sel_groups or None,
            sel_mus or None,
            sel_eq or None,
            name_filter or None,
        )
        with st.expander("Exercise List", expanded=True):
            choice = st.selectbox("Exercise", [""] + names, key="lib_ex_name")
            if choice and st.button("Show Details", key="lib_ex_btn"):
                detail = self.exercise_catalog.fetch_detail(choice)
                if detail:
                    (
                        group,
                        variants,
                        equipment_names,
                        primary,
                        secondary,
                        tertiary,
                        other,
                        _,
                    ) = detail
                    with st.dialog("Exercise Details"):
                        st.markdown(f"**Group:** {group}")
                        st.markdown(f"**Primary:** {primary}")
                        if secondary:
                            st.markdown("**Secondary:**")
                            for m in secondary.split("|"):
                                st.markdown(f"- {m}")
                        if tertiary:
                            st.markdown("**Tertiary:**")
                            for m in tertiary.split("|"):
                                st.markdown(f"- {m}")
                        if other:
                            st.markdown("**Other:**")
                            for m in other.split("|"):
                                st.markdown(f"- {m}")
                        if variants:
                            st.markdown("**Variants:**")
                            for v in variants.split("|"):
                                st.markdown(f"- {v}")

    def _custom_exercise_management(self) -> None:
        muscles = self.muscles_repo.fetch_all()
        groups = self.exercise_catalog.fetch_muscle_groups()
        equipment_names = self.equipment.fetch_names()

        with st.expander("Add Custom Exercise"):
            group = st.selectbox("Muscle Group", groups, key="cust_ex_group")
            name = st.text_input("Exercise Name", key="cust_ex_name")
            variants = st.text_input("Variants", key="cust_ex_variants")
            eq_sel = st.multiselect("Equipment", equipment_names, key="cust_ex_eq")
            primary = st.selectbox("Primary Muscle", muscles, key="cust_ex_primary")
            secondary = st.multiselect("Secondary", muscles, key="cust_ex_sec")
            tertiary = st.multiselect("Tertiary", muscles, key="cust_ex_ter")
            other = st.multiselect("Other", muscles, key="cust_ex_other")
            if st.button("Add Exercise", key="cust_ex_add"):
                if name:
                    try:
                        self.exercise_catalog.add(
                            group,
                            name,
                            variants,
                            "|".join(eq_sel),
                            primary,
                            "|".join(secondary),
                            "|".join(tertiary),
                            "|".join(other),
                        )
                        st.success("Exercise added")
                    except ValueError as e:
                        st.warning(str(e))
                else:
                    st.warning("Name required")

        with st.expander("Custom Exercise List", expanded=True):
            records = self.exercise_catalog.fetch_all_records(custom_only=True)
            for (
                name,
                group,
                variants,
                eq_names,
                primary,
                secondary,
                tertiary,
                other,
                _,
            ) in records:
                exp = st.expander(name)
                with exp:
                    edit_name = st.text_input("Name", name, key=f"cust_name_{name}")
                    edit_group = st.text_input("Group", group, key=f"cust_group_{name}")
                    edit_var = st.text_input(
                        "Variants", variants, key=f"cust_var_{name}"
                    )
                    edit_eq = st.text_input(
                        "Equipment", eq_names, key=f"cust_eq_{name}"
                    )
                    edit_primary = st.text_input(
                        "Primary", primary, key=f"cust_pri_{name}"
                    )
                    edit_secondary = st.text_input(
                        "Secondary", secondary, key=f"cust_sec_{name}"
                    )
                    edit_tertiary = st.text_input(
                        "Tertiary", tertiary, key=f"cust_ter_{name}"
                    )
                    edit_other = st.text_input("Other", other, key=f"cust_oth_{name}")
                    cols = st.columns(2)
                    if cols[0].button("Update", key=f"upd_cust_{name}"):
                        try:
                            self.exercise_catalog.update(
                                name,
                                edit_group,
                                edit_var,
                                edit_eq,
                                edit_primary,
                                edit_secondary,
                                edit_tertiary,
                                edit_other,
                                new_name=edit_name,
                            )
                            st.success("Updated")
                        except ValueError as e:
                            st.warning(str(e))
                    if cols[1].button("Delete", key=f"del_cust_{name}"):
                        try:
                            self.exercise_catalog.remove(name)
                            st.success("Deleted")
                        except ValueError as e:
                            st.warning(str(e))

    def _history_tab(self) -> None:
        st.header("Workout History")
        favs = self.favorite_workouts_repo.fetch_all()
        with st.expander("Favorite Workouts", expanded=True):
            if favs:
                for fid in favs:
                    try:
                        _id, date, *_ = self.workouts.fetch_detail(fid)
                    except ValueError:
                        continue
                    cols = st.columns(2)
                    cols[0].write(date)
                    if cols[1].button("Remove", key=f"fav_wk_rm_{fid}"):
                        self.favorite_workouts_repo.remove(fid)
                        st.experimental_rerun()
            else:
                st.write("No favorites.")
            all_workouts = {str(w[0]): w[1] for w in self.workouts.fetch_all_workouts()}
            add_choice = st.selectbox(
                "Add Favorite",
                [""] + list(all_workouts.keys()),
                format_func=lambda x: "" if x == "" else all_workouts[x],
                key="fav_wk_add_choice",
            )
            if st.button("Add Favorite", key="fav_wk_add_btn") and add_choice:
                self.favorite_workouts_repo.add(int(add_choice))
                st.experimental_rerun()
        with st.expander("Filters", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="hist_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="hist_end")
            ttype = st.selectbox(
                "Training Type",
                ["", "strength", "hypertrophy", "highintensity"],
                key="hist_type",
            )
            start_str = start.isoformat()
            end_str = end.isoformat()
        workouts = self.workouts.fetch_all_workouts(start_str, end_str)
        if ttype:
            workouts = [w for w in workouts if w[4] == ttype]
        for wid, date, _s, _e, training_type, *_ in workouts:
            with st.expander(f"{date} ({training_type})", expanded=False):
                summary = self.sets.workout_summary(wid)
                st.markdown(
                    f"**Volume:** {summary['volume']} | **Sets:** {summary['sets']} | **Avg RPE:** {summary['avg_rpe']}"
                )
                if st.button("Details", key=f"hist_det_{wid}"):
                    self._workout_details_dialog(wid)

    def _workout_details_dialog(self, workout_id: int) -> None:
        exercises = self.exercises.fetch_for_workout(workout_id)
        with st.dialog("Workout Details"):
            for ex_id, name, eq, note in exercises:
                sets = self.sets.fetch_for_exercise(ex_id)
                header = name if not eq else f"{name} ({eq})"
                if note:
                    header += f" - {note}"
                with st.expander(header, expanded=True):
                    for sid, reps, weight, rpe, stime, etime in sets:
                        line = f"{reps} reps x {weight} kg (RPE {rpe})"
                        if stime:
                            line += f" start: {stime}"
                        if etime:
                            line += f" end: {etime}"
                        st.write(line)

    def _stats_tab(self) -> None:
        st.header("Statistics")
        with st.expander("Filters", expanded=True):
            exercises = [""] + self.exercise_names_repo.fetch_all()
            ex_choice = st.selectbox("Exercise", exercises, key="stats_ex")
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="stats_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="stats_end")
            start_str = start.isoformat()
            end_str = end.isoformat()
        summary = self.stats.exercise_summary(
            ex_choice if ex_choice else None,
            start_str,
            end_str,
        )
        over_tab, dist_tab, prog_tab, rec_tab, tsb_tab = st.tabs(
            [
                "Overview",
                "Distributions",
                "Progress",
                "Records",
                "Stress Balance",
            ]
        )
        with over_tab:
            st.table(summary)
            daily = self.stats.daily_volume(start_str, end_str)
            if daily:
                st.line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    x=[d["date"] for d in daily],
                )
            equip_stats = self.stats.equipment_usage(start_str, end_str)
            st.table(equip_stats)
            eff_stats = self.stats.session_efficiency(start_str, end_str)
            if eff_stats:
                with st.expander("Session Efficiency", expanded=False):
                    st.table(eff_stats)
        with dist_tab:
            rpe_dist = self.stats.rpe_distribution(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if rpe_dist:
                st.bar_chart(
                    {"Count": [d["count"] for d in rpe_dist]},
                    x=[str(d["rpe"]) for d in rpe_dist],
                )
            reps_dist = self.stats.reps_distribution(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if reps_dist:
                st.bar_chart(
                    {"Count": [d["count"] for d in reps_dist]},
                    x=[str(d["reps"]) for d in reps_dist],
                )
        with prog_tab:
            if ex_choice:
                prog = self.stats.progression(ex_choice, start_str, end_str)
                if prog:
                    st.line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        x=[p["date"] for p in prog],
                    )
                self._progress_forecast_section(ex_choice)
            self._volume_forecast_section(start_str, end_str)
        with rec_tab:
            records = self.stats.personal_records(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if records:
                st.table(records)
        with tsb_tab:
            tsb = self.stats.stress_balance(start_str, end_str)
            if tsb:
                st.line_chart(
                    {"TSB": [d["tsb"] for d in tsb]}, x=[d["date"] for d in tsb]
                )
            overview = self.stats.stress_overview(start_str, end_str)
            if overview:
                st.metric("Stress", overview["stress"])
                st.metric("Fatigue", overview["fatigue"])

    def _progress_forecast_section(self, exercise: str) -> None:
        st.subheader("Progress Forecast")
        weeks = st.slider("Weeks", 1, 12, 4, key="forecast_weeks")
        wpw = st.slider("Workouts per Week", 1, 7, 3, key="forecast_wpw")
        if st.button("Show Forecast"):
            forecast = self.stats.progress_forecast(exercise, weeks, wpw)
            if forecast:
                st.line_chart(
                    {"Est 1RM": [f["est_1rm"] for f in forecast]},
                    x=[str(f["week"]) for f in forecast],
                )

    def _volume_forecast_section(self, start: str, end: str) -> None:
        st.subheader("Volume Forecast")
        days = st.slider("Days", 1, 14, 7, key="vol_forecast_days")
        if st.button("Show Volume Forecast"):
            data = self.stats.volume_forecast(days, start, end)
            if data:
                st.line_chart(
                    {"Volume": [d["volume"] for d in data]},
                    x=[d["date"] for d in data],
                )

    def _insights_tab(self) -> None:
        st.header("Insights")
        exercises = [""] + self.exercise_names_repo.fetch_all()
        with st.expander("Filters", expanded=True):
            ex_choice = st.selectbox("Exercise", exercises, key="insights_ex")
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=90),
                    key="insights_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="insights_end")
        if ex_choice:
            insights = self.stats.progress_insights(
                ex_choice, start.isoformat(), end.isoformat()
            )
            prog = self.stats.progression(ex_choice, start.isoformat(), end.isoformat())
            if insights:
                with st.expander("Trend Analysis", expanded=True):
                    st.write(f"Trend: {insights.get('trend', '')}")
                    if "slope" in insights:
                        st.metric("Slope", round(insights["slope"], 2))
                    if "r_squared" in insights:
                        st.metric("R\xb2", round(insights["r_squared"], 2))
                    if "strength_seasonality" in insights:
                        st.metric(
                            "Seasonality Strength",
                            round(insights["strength_seasonality"], 2),
                        )
                    st.metric("Plateau Score", insights["plateau_score"])
            if prog:
                with st.expander("1RM Progression", expanded=True):
                    st.line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        x=[p["date"] for p in prog],
                    )
        else:
            st.info("Select an exercise to view insights.")

    def _weight_tab(self) -> None:
        st.header("Body Weight")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="bw_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="bw_end")
            start_str = start.isoformat()
            end_str = end.isoformat()
        stats = self.stats.weight_stats(start_str, end_str)
        with st.expander("Statistics", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("Average", stats["avg"])
            c2.metric("Min", stats["min"])
            c3.metric("Max", stats["max"])
        history = self.stats.body_weight_history(start_str, end_str)
        if history:
            with st.expander("Weight History", expanded=True):
                st.line_chart(
                    {"Weight": [h["weight"] for h in history]},
                    x=[h["date"] for h in history],
                )
        bmi_hist = self.stats.bmi_history(start_str, end_str)
        if bmi_hist:
            with st.expander("BMI History", expanded=False):
                st.line_chart(
                    {"BMI": [b["bmi"] for b in bmi_hist]},
                    x=[b["date"] for b in bmi_hist],
                )
        with st.expander("Forecast", expanded=False):
            days = st.slider("Days", 1, 14, 7, key="bw_fc_days")
            if st.button("Show Forecast", key="bw_fc_btn"):
                forecast = self.stats.weight_forecast(days)
                if forecast:
                    st.line_chart(
                        {"Weight": [f["weight"] for f in forecast]},
                        x=[str(f["day"]) for f in forecast],
                    )

    def _reports_tab(self) -> None:
        st.header("Reports")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="rep_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="rep_end")
            start_str = start.isoformat()
            end_str = end.isoformat()
        with st.expander("Overall Summary", expanded=True):
            summary = self.stats.overview(start_str, end_str)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Workouts", summary["workouts"])
            c2.metric("Volume", summary["volume"])
            c3.metric("Avg RPE", summary["avg_rpe"])
            c4.metric("Exercises", summary["exercises"])
        with st.expander("Top Exercises", expanded=True):
            data = self.stats.exercise_summary(None, start_str, end_str)
            data.sort(key=lambda x: x["volume"], reverse=True)
            if data:
                st.table(data[:5])
        with st.expander("Exercise Frequency", expanded=True):
            freq = self.stats.exercise_frequency(None, start_str, end_str)
            if freq:
                st.table(freq)
        with st.expander("Equipment Usage", expanded=True):
            eq_stats = self.stats.equipment_usage(start_str, end_str)
            if eq_stats:
                st.table(eq_stats)
                st.bar_chart(
                    {"Volume": [e["volume"] for e in eq_stats]},
                    x=[e["equipment"] for e in eq_stats],
                )
        with st.expander("Daily Volume", expanded=True):
            daily = self.stats.daily_volume(start_str, end_str)
            if daily:
                st.line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    x=[d["date"] for d in daily],
                )
        with st.expander("Training Strain", expanded=True):
            strain = self.stats.training_strain(start_str, end_str)
            if strain:
                st.line_chart(
                    {"Strain": [s["strain"] for s in strain]},
                    x=[s["week"] for s in strain],
                )

    def _gamification_tab(self) -> None:
        st.header("Gamification Stats")
        with st.expander("Summary", expanded=True):
            st.metric("Total Points", self.gamification.total_points())
        with st.expander("Points by Workout", expanded=True):
            data = self.gamification.points_by_workout()
            if data:
                st.bar_chart(
                    {"Points": [p[1] for p in data]},
                    x=[str(p[0]) for p in data],
                )

    def _tests_tab(self) -> None:
        st.header("Pyramid Test")
        with st.expander("New Test", expanded=True):
            for idx, val in enumerate(st.session_state.pyramid_inputs):
                st.session_state.pyramid_inputs[idx] = st.number_input(
                    f"Weight {idx + 1} (kg)",
                    min_value=0.0,
                    step=0.5,
                    value=float(val),
                    key=f"pyr_weight_{idx}",
                )
            if st.button("Add Line"):
                st.session_state.pyramid_inputs.append(0.0)
            with st.expander("Additional Details"):
                ex_name = st.text_input("Exercise Name", key="pyr_ex_name")
                eq_name = st.selectbox(
                    "Equipment",
                    [""] + self.equipment.fetch_names(),
                    key="pyr_eq_name",
                )
                start_w = st.number_input(
                    "Starting Weight (kg)",
                    min_value=0.0,
                    step=0.5,
                    key="pyr_start_w",
                )
                failed_w = st.number_input(
                    "Failed Weight (kg)",
                    min_value=0.0,
                    step=0.5,
                    key="pyr_failed_w",
                )
                max_a = st.number_input(
                    "Max Achieved (kg)",
                    min_value=0.0,
                    step=0.5,
                    key="pyr_max_a",
                )
                dur = st.number_input(
                    "Test Duration (min)",
                    min_value=0,
                    step=1,
                    key="pyr_dur",
                )
                rest = st.text_input("Rest Between Attempts", key="pyr_rest")
                rpe_attempt = st.text_input("RPE per Attempt", key="pyr_rpe_a")
                tod = st.text_input("Time of Day", key="pyr_tod")
                sleep_h = st.number_input(
                    "Sleep Hours",
                    min_value=0.0,
                    step=0.5,
                    key="pyr_sleep",
                )
                stress = st.number_input(
                    "Stress Level",
                    min_value=0,
                    step=1,
                    key="pyr_stress",
                )
                nutrition = st.number_input(
                    "Nutrition Quality",
                    min_value=0,
                    step=1,
                    key="pyr_nutrition",
                )
            if st.button("Save Pyramid Test"):
                weights = [
                    float(st.session_state.get(f"pyr_weight_{i}", 0.0))
                    for i in range(len(st.session_state.pyramid_inputs))
                ]
                weights = [w for w in weights if w > 0.0]
                if weights:
                    tid = self.pyramid_tests.create(
                        datetime.date.today().isoformat(),
                        exercise_name=ex_name or "Unknown",
                        equipment_name=eq_name or None,
                        starting_weight=start_w if start_w > 0 else None,
                        failed_weight=failed_w if failed_w > 0 else None,
                        max_achieved=max_a if max_a > 0 else None,
                        test_duration_minutes=dur if dur > 0 else None,
                        rest_between_attempts=rest or None,
                        rpe_per_attempt=rpe_attempt or None,
                        time_of_day=tod or None,
                        sleep_hours=sleep_h if sleep_h > 0 else None,
                        stress_level=stress if stress > 0 else None,
                        nutrition_quality=nutrition if nutrition > 0 else None,
                    )
                    for w in weights:
                        self.pyramid_entries.add(tid, w)
                    st.success("Saved")
                else:
                    st.warning("Enter weights")
                st.session_state.pyramid_inputs = [0.0]
                for i in range(len(weights)):
                    st.session_state.pop(f"pyr_weight_{i}", None)
                for key in [
                    "pyr_ex_name",
                    "pyr_eq_name",
                    "pyr_start_w",
                    "pyr_failed_w",
                    "pyr_max_a",
                    "pyr_dur",
                    "pyr_rest",
                    "pyr_rpe_a",
                    "pyr_tod",
                    "pyr_sleep",
                    "pyr_stress",
                    "pyr_nutrition",
                ]:
                    st.session_state.pop(key, None)

        history = self.pyramid_tests.fetch_all_with_weights(self.pyramid_entries)
        if history:
            with st.expander("History", expanded=True):
                display = [
                    {"date": d, "weights": "|".join([str(w) for w in ws])}
                    for _tid, d, ws in history
                ]
                st.table(display)

        with st.expander("Warmup Calculator", expanded=False):
            tgt = st.number_input(
                "Target Weight (kg)", min_value=0.0, step=0.5, key="warmup_target"
            )
            count = st.number_input(
                "Warmup Sets", min_value=1, step=1, value=3, key="warmup_sets"
            )
            if st.button("Calculate Warmup", key="warmup_calc"):
                try:
                    weights = MathTools.warmup_weights(float(tgt), int(count))
                    st.table(
                        [{"set": i + 1, "weight": w} for i, w in enumerate(weights)]
                    )
                except ValueError as e:
                    st.warning(str(e))

    def _settings_tab(self) -> None:
        st.header("Settings")
        if "delete_target" not in st.session_state:
            st.session_state.delete_target = None

        with st.expander("Data Deletion", expanded=True):
            if st.button("Delete All Logged and Planned Workouts"):
                st.session_state.delete_target = "all"
            if st.button("Delete All Logged Workouts"):
                st.session_state.delete_target = "logged"
            if st.button("Delete All Planned Workouts"):
                st.session_state.delete_target = "planned"

        target = st.session_state.get("delete_target")
        if target:
            with st.dialog("Confirm Deletion"):
                text = st.text_input("Type 'Yes, I confirm' to delete")
                if st.button("Confirm"):
                    if text == "Yes, I confirm":
                        if target == "all":
                            self.workouts.delete_all()
                            self.planned_workouts.delete_all()
                        elif target == "logged":
                            self.workouts.delete_all()
                        elif target == "planned":
                            self.planned_workouts.delete_all()
                        st.success("Data deleted")
                        st.session_state.delete_target = None
                    else:
                        st.warning("Confirmation failed")
                if st.button("Cancel"):
                    st.session_state.delete_target = None

        (
            gen_tab,
            eq_tab,
            mus_tab,
            ex_tab,
            cust_tab,
            bw_tab,
            well_tab,
            tag_tab,
        ) = st.tabs(
            [
                "General",
                "Equipment",
                "Muscles",
                "Exercise Aliases",
                "Custom Exercises",
                "Body Weight Logs",
                "Wellness Logs",
                "Workout Tags",
            ]
        )

        with gen_tab:
            st.header("General Settings")
            with st.expander("User Settings", expanded=True):
                bw = st.number_input(
                    "Body Weight (kg)",
                    min_value=1.0,
                    value=self.settings_repo.get_float("body_weight", 80.0),
                    step=0.5,
                )
                height = st.number_input(
                    "Height (m)",
                    min_value=0.5,
                    value=self.settings_repo.get_float("height", 1.75),
                    step=0.01,
                )
                ma = st.number_input(
                    "Months Active",
                    min_value=0.0,
                    value=self.settings_repo.get_float("months_active", 1.0),
                    step=1.0,
                )
                theme_opt = st.selectbox(
                    "Theme",
                    ["light", "dark"],
                    index=["light", "dark"].index(self.theme),
                )
            with st.expander("Gamification", expanded=True):
                game_enabled = st.checkbox(
                    "Enable Gamification",
                    value=self.gamification.is_enabled(),
                )
                st.metric("Total Points", self.gamification.total_points())
            with st.expander("Machine Learning", expanded=True):
                ml_global = st.checkbox(
                    "Enable ML Models",
                    value=self.settings_repo.get_bool("ml_all_enabled", True),
                )
                ml_train = st.checkbox(
                    "Enable ML Training",
                    value=self.settings_repo.get_bool("ml_training_enabled", True),
                )
                ml_pred = st.checkbox(
                    "Enable ML Prediction",
                    value=self.settings_repo.get_bool("ml_prediction_enabled", True),
                )
                rpe_train = st.checkbox(
                    "RPE Model Training",
                    value=self.settings_repo.get_bool("ml_rpe_training_enabled", True),
                )
                rpe_pred = st.checkbox(
                    "RPE Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_rpe_prediction_enabled", True
                    ),
                )
                vol_train = st.checkbox(
                    "Volume Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_volume_training_enabled", True
                    ),
                )
                vol_pred = st.checkbox(
                    "Volume Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_volume_prediction_enabled", True
                    ),
                )
                read_train = st.checkbox(
                    "Readiness Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_readiness_training_enabled", True
                    ),
                )
                read_pred = st.checkbox(
                    "Readiness Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_readiness_prediction_enabled", True
                    ),
                )
                prog_train = st.checkbox(
                    "Progress Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_progress_training_enabled", True
                    ),
                )
                prog_pred = st.checkbox(
                    "Progress Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_progress_prediction_enabled", True
                    ),
                )
                goal_train = st.checkbox(
                    "Goal Model Training",
                    value=self.settings_repo.get_bool("ml_goal_training_enabled", True),
                )
                goal_pred = st.checkbox(
                    "Goal Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_goal_prediction_enabled", True
                    ),
                )
                inj_train = st.checkbox(
                    "Injury Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_injury_training_enabled", True
                    ),
                )
                inj_pred = st.checkbox(
                    "Injury Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_injury_prediction_enabled", True
                    ),
                )
            if st.button("Save General Settings"):
                self.settings_repo.set_float("body_weight", bw)
                self.settings_repo.set_float("height", height)
                self.settings_repo.set_float("months_active", ma)
                self.settings_repo.set_text("theme", theme_opt)
                self.theme = theme_opt
                self._apply_theme()
                self.gamification.enable(game_enabled)
                self.settings_repo.set_bool("ml_all_enabled", ml_global)
                self.settings_repo.set_bool("ml_training_enabled", ml_train)
                self.settings_repo.set_bool("ml_prediction_enabled", ml_pred)
                self.settings_repo.set_bool("ml_rpe_training_enabled", rpe_train)
                self.settings_repo.set_bool("ml_rpe_prediction_enabled", rpe_pred)
                self.settings_repo.set_bool("ml_volume_training_enabled", vol_train)
                self.settings_repo.set_bool("ml_volume_prediction_enabled", vol_pred)
                self.settings_repo.set_bool("ml_readiness_training_enabled", read_train)
                self.settings_repo.set_bool(
                    "ml_readiness_prediction_enabled", read_pred
                )
                self.settings_repo.set_bool("ml_progress_training_enabled", prog_train)
                self.settings_repo.set_bool("ml_progress_prediction_enabled", prog_pred)
                self.settings_repo.set_bool("ml_goal_training_enabled", goal_train)
                self.settings_repo.set_bool("ml_goal_prediction_enabled", goal_pred)
                self.settings_repo.set_bool("ml_injury_training_enabled", inj_train)
                self.settings_repo.set_bool("ml_injury_prediction_enabled", inj_pred)
                st.success("Settings saved")

        with eq_tab:
            st.header("Equipment Management")
            with st.expander("Add Equipment"):
                muscles_list = self.muscles_repo.fetch_all()
                new_name = st.text_input("Equipment Name", key="equip_new_name")
                types = self.equipment.fetch_types()
                type_choice = st.selectbox(
                    "Equipment Type", types, key="equip_new_type"
                )
                new_muscles = st.multiselect(
                    "Muscles", muscles_list, key="equip_new_muscles"
                )
                if st.button("Add Equipment"):
                    if new_name and type_choice and new_muscles:
                        try:
                            self.equipment.add(type_choice, new_name, new_muscles)
                            st.success("Equipment added")
                        except ValueError as e:
                            st.warning(str(e))
                    else:
                        st.warning("All fields required")

            with st.expander("Equipment List", expanded=True):
                for (
                    name,
                    eq_type,
                    muscles,
                    is_custom,
                ) in self.equipment.fetch_all_records():
                    exp = st.expander(name)
                    with exp:
                        musc_list = muscles.split("|")
                        if is_custom:
                            edit_name = st.text_input(
                                "Name", name, key=f"edit_name_{name}"
                            )
                            edit_type = st.text_input(
                                "Type", eq_type, key=f"edit_type_{name}"
                            )
                            edit_muscles = st.multiselect(
                                "Muscles",
                                muscles_list,
                                musc_list,
                                key=f"edit_mus_{name}",
                            )
                            if st.button("Update", key=f"upd_eq_{name}"):
                                try:
                                    self.equipment.update(
                                        name, edit_type, edit_muscles, edit_name
                                    )
                                    st.success("Updated")
                                except ValueError as e:
                                    st.warning(str(e))
                            if st.button("Delete", key=f"del_eq_{name}"):
                                try:
                                    self.equipment.remove(name)
                                    st.success("Deleted")
                                except ValueError as e:
                                    st.warning(str(e))
                        else:
                            st.markdown(f"**Type:** {eq_type}")
                            st.markdown("**Muscles:**")
                            for m in musc_list:
                                st.markdown(f"- {m}")

        with mus_tab:
            st.header("Muscle Linking")
            muscles = self.muscles_repo.fetch_all()
            with st.expander("Link Muscles"):
                if muscles:
                    col1, col2 = st.columns(2)
                    with col1:
                        m1 = st.selectbox("Muscle 1", muscles, key="link_m1")
                    with col2:
                        m2 = st.selectbox("Muscle 2", muscles, key="link_m2")
                    if st.button("Link Muscles"):
                        self.muscles_repo.link(m1, m2)
                        st.success("Linked")

            with st.expander("Add Alias", expanded=True):
                new_muscle = st.text_input("New Muscle Name", key="new_muscle")
                link_to = st.selectbox("Link To", muscles, key="link_to")
                if st.button("Add Alias"):
                    if new_muscle:
                        self.muscles_repo.add_alias(new_muscle, link_to)
                        st.success("Alias added")
                    else:
                        st.warning("Name required")

        with ex_tab:
            st.header("Exercise Aliases")
            names = self.exercise_names_repo.fetch_all()
            with st.expander("Link Exercises"):
                if names:
                    col1, col2 = st.columns(2)
                    with col1:
                        e1 = st.selectbox("Exercise 1", names, key="link_ex1")
                    with col2:
                        e2 = st.selectbox("Exercise 2", names, key="link_ex2")
                    if st.button("Link Exercises"):
                        self.exercise_names_repo.link(e1, e2)
                        st.success("Linked")

            with st.expander("Add Exercise Alias", expanded=True):
                new_ex = st.text_input("New Exercise Name", key="new_ex_alias")
                link_ex = st.selectbox("Link To", names, key="link_ex_to")
                if st.button("Add Exercise Alias"):
                    if new_ex:
                        self.exercise_names_repo.add_alias(new_ex, link_ex)
                        st.success("Alias added")
                    else:
                        st.warning("Name required")

        with cust_tab:
            st.header("Custom Exercises")
            self._custom_exercise_management()

        with bw_tab:
            st.header("Body Weight Logs")
            with st.expander("Add Entry"):
                bw_date = st.date_input(
                    "Date",
                    datetime.date.today(),
                    key="bw_date",
                )
                bw_val = st.number_input(
                    "Weight (kg)",
                    min_value=1.0,
                    step=0.1,
                    key="bw_val",
                )
                if st.button("Log Weight", key="bw_add"):
                    try:
                        self.body_weights_repo.log(bw_date.isoformat(), bw_val)
                        st.success("Logged")
                    except ValueError as e:
                        st.warning(str(e))

            with st.expander("History", expanded=True):
                rows = self.body_weights_repo.fetch_history()
                for rid, d, w in rows:
                    exp = st.expander(f"{d} - {w} kg")
                    with exp:
                        date_edit = st.date_input(
                            "Date",
                            datetime.date.fromisoformat(d),
                            key=f"bw_edit_date_{rid}",
                        )
                        weight_edit = st.number_input(
                            "Weight (kg)",
                            value=w,
                            min_value=1.0,
                            step=0.1,
                            key=f"bw_edit_val_{rid}",
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"bw_upd_{rid}"):
                            try:
                                self.body_weights_repo.update(
                                    rid,
                                    date_edit.isoformat(),
                                    weight_edit,
                                )
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"bw_del_{rid}"):
                            try:
                                self.body_weights_repo.delete(rid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))

            with st.expander("BMI History", expanded=False):
                bmi_hist = self.stats.bmi_history()
                if bmi_hist:
                    st.line_chart(
                        {"BMI": [b["bmi"] for b in bmi_hist]},
                        x=[b["date"] for b in bmi_hist],
                    )

        with well_tab:
            st.header("Wellness Logs")
            with st.expander("Add Entry"):
                w_date = st.date_input(
                    "Date",
                    datetime.date.today(),
                    key="well_date",
                )
                calories = st.number_input(
                    "Calories", min_value=0.0, step=50.0, key="well_calories"
                )
                sleep_h = st.number_input(
                    "Sleep Hours", min_value=0.0, step=0.5, key="well_sleep"
                )
                sleep_q = st.number_input(
                    "Sleep Quality",
                    min_value=0.0,
                    max_value=5.0,
                    step=1.0,
                    key="well_quality",
                )
                stress = st.number_input(
                    "Stress Level", min_value=0, max_value=10, step=1, key="well_stress"
                )
                if st.button("Log Wellness", key="well_add"):
                    try:
                        self.wellness_repo.log(
                            w_date.isoformat(),
                            calories,
                            sleep_h,
                            sleep_q,
                            int(stress),
                        )
                        st.success("Logged")
                    except ValueError as e:
                        st.warning(str(e))

            with st.expander("History", expanded=True):
                rows = self.wellness_repo.fetch_history()
                for rid, d, cal, sh, sq, st_lvl in rows:
                    exp = st.expander(f"{d}")
                    with exp:
                        date_e = st.date_input(
                            "Date",
                            datetime.date.fromisoformat(d),
                            key=f"well_edit_date_{rid}",
                        )
                        cal_e = st.number_input(
                            "Calories",
                            value=cal or 0.0,
                            step=50.0,
                            key=f"well_edit_cal_{rid}",
                        )
                        sh_e = st.number_input(
                            "Sleep Hours",
                            value=sh or 0.0,
                            step=0.5,
                            key=f"well_edit_sleep_{rid}",
                        )
                        sq_e = st.number_input(
                            "Sleep Quality",
                            value=sq or 0.0,
                            step=1.0,
                            key=f"well_edit_quality_{rid}",
                        )
                        st_e = st.number_input(
                            "Stress Level",
                            value=st_lvl or 0,
                            step=1,
                            key=f"well_edit_stress_{rid}",
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"well_upd_{rid}"):
                            try:
                                self.wellness_repo.update(
                                    rid,
                                    date_e.isoformat(),
                                    cal_e,
                                    sh_e,
                                    sq_e,
                                    int(st_e),
                                )
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"well_del_{rid}"):
                            try:
                                self.wellness_repo.delete(rid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))

        with tag_tab:
            st.header("Workout Tags")
            with st.expander("Add Tag"):
                tag_name = st.text_input("Name", key="new_tag")
                if st.button("Add Tag", key="add_tag"):
                    if tag_name:
                        try:
                            self.tags_repo.add(tag_name)
                            st.success("Added")
                        except Exception as e:
                            st.warning(str(e))
                    else:
                        st.warning("Name required")

            with st.expander("Existing Tags", expanded=True):
                tags = self.tags_repo.fetch_all()
                for tid, name in tags:
                    exp = st.expander(name)
                    with exp:
                        name_edit = st.text_input(
                            "Name", value=name, key=f"tag_name_{tid}"
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"tag_upd_{tid}"):
                            try:
                                self.tags_repo.update(tid, name_edit)
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"tag_del_{tid}"):
                            try:
                                self.tags_repo.delete(tid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))


if __name__ == "__main__":
    GymApp().run()
