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
    EquipmentRepository,
    ExerciseCatalogRepository,
    MuscleRepository,
    ExerciseNameRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
)
from planner_service import PlannerService
from recommendation_service import RecommendationService
from stats_service import StatisticsService


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(self) -> None:
        self._configure_page()
        self._inject_responsive_css()
        self.workouts = WorkoutRepository()
        self.exercises = ExerciseRepository()
        self.sets = SetRepository()
        self.planned_workouts = PlannedWorkoutRepository()
        self.planned_exercises = PlannedExerciseRepository()
        self.planned_sets = PlannedSetRepository()
        self.equipment = EquipmentRepository()
        self.exercise_catalog = ExerciseCatalogRepository()
        self.muscles_repo = MuscleRepository()
        self.exercise_names_repo = ExerciseNameRepository()
        self.settings_repo = SettingsRepository()
        self.pyramid_tests = PyramidTestRepository()
        self.pyramid_entries = PyramidEntryRepository()
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
        )
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
        )
        self.stats = StatisticsService(
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
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
        st.set_page_config(
            page_title="Workout Logger",
            layout="centered" if mode == "mobile" else "wide",
        )
        st.session_state.layout_set = True
        st.session_state.is_mobile = mode == "mobile"

    def _inject_responsive_css(self) -> None:
        st.markdown(
            """
            <style>
            @media screen and (max-width: 768px) {
                div[data-testid="column"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                }
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
        if "pyramid_inputs" not in st.session_state:
            st.session_state.pyramid_inputs = [0.0]

    def _dashboard_tab(self) -> None:
        st.header("Dashboard")
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
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Workouts", stats["workouts"])
        m2.metric("Volume", stats["volume"])
        m3.metric("Avg RPE", stats["avg_rpe"])
        m4.metric("Exercises", stats["exercises"])
        daily = self.stats.daily_volume(start.isoformat(), end.isoformat())
        st.subheader("Daily Volume")
        if daily:
            st.line_chart({"Volume": [d["volume"] for d in daily]}, x=[d["date"] for d in daily])
        exercises = [""] + self.exercise_names_repo.fetch_all()
        ex_choice = st.selectbox("Exercise Progression", exercises, key="dash_ex")
        if ex_choice:
            prog = self.stats.progression(ex_choice, start.isoformat(), end.isoformat())
            st.subheader("1RM Progression")
            if prog:
                st.line_chart({"1RM": [p["est_1rm"] for p in prog]}, x=[p["date"] for p in prog])

    def run(self) -> None:
        st.title("Workout Logger")
        self._refresh()
        dash_tab, log_tab, plan_tab, stats_tab, tests_tab, settings_tab = st.tabs([
            "Dashboard",
            "Log",
            "Plan",
            "Stats",
            "Tests",
            "Settings",
        ])
        with dash_tab:
            self._dashboard_tab()
        with log_tab:
            self._log_tab()
        with plan_tab:
            self._plan_tab()
        with stats_tab:
            self._stats_tab()
        with tests_tab:
            self._tests_tab()
        with settings_tab:
            self._settings_tab()

    def _log_tab(self) -> None:
        plans = self.planned_workouts.fetch_all()
        options = {str(p[0]): p for p in plans}
        if options:
            selected = st.selectbox(
                "Planned Workout", [""] + list(options.keys()),
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
        self._planned_workout_section()
        if st.session_state.selected_planned_workout:
            self._planned_exercise_section()

    def _workout_section(self) -> None:
        st.header("Workouts")
        training_options = ["strength", "hypertrophy", "highintensity"]
        with st.expander("Create New Workout"):
            new_type = st.selectbox("Training Type", training_options, key="new_workout_type")
            if st.button("New Workout"):
                new_id = self.workouts.create(
                    datetime.date.today().isoformat(), new_type
                )
                st.session_state.selected_workout = new_id
        with st.expander("Existing Workouts", expanded=True):
            workouts = self.workouts.fetch_all_workouts()
            options = {str(w[0]): w for w in workouts}
            if options:
                selected = st.selectbox(
                    "Select Workout", list(options.keys()),
                    format_func=lambda x: options[x][1]
                )
                st.session_state.selected_workout = int(selected)
                detail = self.workouts.fetch_detail(int(selected))
                start_time = detail[2]
                end_time = detail[3]
                current_type = detail[4]
                cols = st.columns(3)
                if cols[0].button("Start Workout", key=f"start_workout_{selected}"):
                    self.workouts.set_start_time(
                        int(selected),
                        datetime.datetime.now().isoformat(timespec="seconds"),
                    )
                if cols[1].button("Finish Workout", key=f"finish_workout_{selected}"):
                    self.workouts.set_end_time(
                        int(selected),
                        datetime.datetime.now().isoformat(timespec="seconds"),
                    )
                type_choice = cols[2].selectbox(
                    "Type",
                    training_options,
                    index=training_options.index(current_type),
                    key=f"type_select_{selected}"
                )
                if cols[2].button("Save", key=f"save_type_{selected}"):
                    self.workouts.set_training_type(int(selected), type_choice)
                if start_time:
                    st.write(f"Start: {start_time}")
                if end_time:
                    st.write(f"End: {end_time}")
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
            if st.button("Add Exercise"):
                if ex_name and eq:
                    self.exercises.add(workout_id, ex_name, eq)
                else:
                    st.warning("Exercise and equipment required")
        with st.expander("Logged Exercises", expanded=True):
            exercises = self.exercises.fetch_for_workout(workout_id)
            for ex_id, name, eq_name in exercises:
                self._exercise_card(ex_id, name, eq_name)

    def _exercise_card(self, exercise_id: int, name: str, equipment: Optional[str]) -> None:
        sets = self.sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
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
            for set_id, reps, weight, rpe, start_time, end_time in sets:
                detail = self.sets.fetch_detail(set_id)
                cols = st.columns(11)
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
                cols[4].write(f"{detail['diff_reps']:+}")
                cols[5].write(f"{detail['diff_weight']:+.1f}")
                cols[6].write(f"{detail['diff_rpe']:+}")
                if cols[7].button("Start", key=f"start_set_{set_id}"):
                    self.sets.set_start_time(
                        set_id,
                        datetime.datetime.now().isoformat(timespec="seconds"),
                    )
                if cols[8].button("Finish", key=f"finish_set_{set_id}"):
                    self.sets.set_end_time(
                        set_id,
                        datetime.datetime.now().isoformat(timespec="seconds"),
                    )
                if cols[9].button("Delete", key=f"del_{set_id}"):
                    self.sets.remove(set_id)
                    continue
                if cols[10].button("Update", key=f"upd_{set_id}"):
                    self.sets.update(
                        set_id, int(reps_val), float(weight_val), int(rpe_val)
                    )
                if start_time:
                    cols[7].write(start_time)
                if end_time:
                    cols[8].write(end_time)
            hist = self.stats.exercise_history(name)
            if hist:
                with st.expander("History (last 5)"):
                    st.table(hist[-5:][::-1])
            if self.recommender.has_history(name):
                if st.button("Recommend Next Set", key=f"rec_next_{exercise_id}"):
                    try:
                        self.recommender.recommend_next_set(exercise_id)
                    except ValueError as e:
                        st.warning(str(e))
            self._add_set_form(exercise_id)

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
        if st.button("Add Set", key=f"add_set_{exercise_id}"):
            self.sets.add(exercise_id, int(reps), float(weight), int(rpe))
            st.session_state.pop(f"new_reps_{exercise_id}", None)
            st.session_state.pop(f"new_weight_{exercise_id}", None)
            st.session_state.pop(f"new_rpe_{exercise_id}", None)

    def _equipment_selector(self, prefix: str, muscles: Optional[list] = None) -> Optional[str]:
        types = [""] + self.equipment.fetch_types()
        eq_type = st.selectbox("Equipment Type", types, key=f"{prefix}_type")
        filter_text = st.text_input("Filter Equipment", key=f"{prefix}_filter")
        names = self.equipment.fetch_names(
            eq_type if eq_type else None,
            filter_text or None,
            muscles,
        )
        eq_name = st.selectbox("Equipment Name", ["" ] + names, key=f"{prefix}_name")
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
        names = self.exercise_catalog.fetch_names(
            group_sel or None,
            muscle_sel or None,
            equipment,
        )
        ex_name = st.selectbox("Exercise", ["" ] + names, key=f"{prefix}_exercise")
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
        with st.expander("Create New Plan"):
            plan_date = st.date_input("Plan Date", datetime.date.today(), key="plan_date")
            if st.button("New Planned Workout"):
                pid = self.planned_workouts.create(plan_date.isoformat())
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

    def _planned_exercise_section(self) -> None:
        st.header("Planned Exercises")
        workout_id = st.session_state.selected_planned_workout
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

    def _planned_exercise_card(self, exercise_id: int, name: str, equipment: Optional[str]) -> None:
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
            for set_id, reps, weight, rpe in sets:
                cols = st.columns(5)
                with cols[0]:
                    st.write(f"Set {set_id}")
                cols[1].number_input(
                    "Reps",
                    min_value=1,
                    step=1,
                    value=int(reps),
                    key=f"plan_reps_{set_id}",
                )
                cols[2].number_input(
                    "Weight (kg)",
                    min_value=0.0,
                    step=0.5,
                    value=float(weight),
                    key=f"plan_weight_{set_id}",
                )
                cols[3].selectbox(
                    "RPE",
                    options=list(range(11)),
                    index=int(rpe),
                    key=f"plan_rpe_{set_id}",
                )
                if cols[4].button("Delete", key=f"del_plan_set_{set_id}"):
                    self.planned_sets.remove(set_id)
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

    def _stats_tab(self) -> None:
        st.header("Statistics")
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
        st.subheader("Summary")
        st.table(summary)
        daily = self.stats.daily_volume(start_str, end_str)
        st.subheader("Daily Volume")
        if daily:
            st.line_chart({"Volume": [d["volume"] for d in daily]}, x=[d["date"] for d in daily])
        equip_stats = self.stats.equipment_usage(start_str, end_str)
        st.subheader("Equipment Usage")
        st.table(equip_stats)
        rpe_dist = self.stats.rpe_distribution(
            ex_choice if ex_choice else None,
            start_str,
            end_str,
        )
        st.subheader("RPE Distribution")
        if rpe_dist:
            st.bar_chart({"Count": [d["count"] for d in rpe_dist]}, x=[str(d["rpe"]) for d in rpe_dist])
        reps_dist = self.stats.reps_distribution(
            ex_choice if ex_choice else None,
            start_str,
            end_str,
        )
        st.subheader("Reps Distribution")
        if reps_dist:
            st.bar_chart({"Count": [d["count"] for d in reps_dist]}, x=[str(d["reps"]) for d in reps_dist])
        if ex_choice:
            prog = self.stats.progression(ex_choice, start_str, end_str)
            st.subheader("1RM Progression")
            if prog:
                st.line_chart({"1RM": [p["est_1rm"] for p in prog]}, x=[p["date"] for p in prog])
            self._progress_forecast_section(ex_choice)

    def _progress_forecast_section(self, exercise: str) -> None:
        st.subheader("Progress Forecast")
        weeks = st.slider("Weeks", 1, 12, 4, key="forecast_weeks")
        wpw = st.slider("Workouts per Week", 1, 7, 3, key="forecast_wpw")
        if st.button("Show Forecast"):
            forecast = self.stats.progress_forecast(exercise, weeks, wpw)
            if forecast:
                st.line_chart({"Est 1RM": [f["est_1rm"] for f in forecast]}, x=[str(f["week"]) for f in forecast])

    def _tests_tab(self) -> None:
        st.header("Pyramid Test")
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
        if st.button("Save Pyramid Test"):
            weights = [float(st.session_state.get(f"pyr_weight_{i}", 0.0)) for i in range(len(st.session_state.pyramid_inputs))]
            weights = [w for w in weights if w > 0.0]
            if weights:
                tid = self.pyramid_tests.create(datetime.date.today().isoformat())
                for w in weights:
                    self.pyramid_entries.add(tid, w)
                st.success("Saved")
            else:
                st.warning("Enter weights")
            st.session_state.pyramid_inputs = [0.0]
            for i in range(len(weights)):
                st.session_state.pop(f"pyr_weight_{i}", None)

        history = self.pyramid_tests.fetch_all_with_weights(self.pyramid_entries)
        if history:
            st.subheader("History")
            display = [
                {"date": d, "weights": "|".join([str(w) for w in ws])}
                for _tid, d, ws in history
            ]
            st.table(display)

    def _settings_tab(self) -> None:
        st.header("Settings")
        if "delete_target" not in st.session_state:
            st.session_state.delete_target = None

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

        gen_tab, eq_tab, mus_tab, ex_tab = st.tabs([
            "General",
            "Equipment",
            "Muscles",
            "Exercise Aliases",
        ])

        with gen_tab:
            st.header("General Settings")
            bw = st.number_input(
                "Body Weight (kg)",
                min_value=1.0,
                value=self.settings_repo.get_float("body_weight", 80.0),
                step=0.5,
            )
            ma = st.number_input(
                "Months Active",
                min_value=0.0,
                value=self.settings_repo.get_float("months_active", 1.0),
                step=1.0,
            )
            if st.button("Save General Settings"):
                self.settings_repo.set_float("body_weight", bw)
                self.settings_repo.set_float("months_active", ma)
                st.success("Settings saved")

        with eq_tab:
            st.header("Equipment Management")
            muscles_list = self.muscles_repo.fetch_all()
            new_name = st.text_input("Equipment Name", key="equip_new_name")
            types = self.equipment.fetch_types()
            type_choice = st.selectbox("Equipment Type", types, key="equip_new_type")
            new_muscles = st.multiselect("Muscles", muscles_list, key="equip_new_muscles")
            if st.button("Add Equipment"):
                if new_name and type_choice and new_muscles:
                    try:
                        self.equipment.add(type_choice, new_name, new_muscles)
                        st.success("Equipment added")
                    except ValueError as e:
                        st.warning(str(e))
                else:
                    st.warning("All fields required")

            for name, eq_type, muscles, is_custom in self.equipment.fetch_all_records():
                exp = st.expander(name)
                with exp:
                    musc_list = muscles.split("|")
                    if is_custom:
                        edit_name = st.text_input("Name", name, key=f"edit_name_{name}")
                        edit_type = st.text_input("Type", eq_type, key=f"edit_type_{name}")
                        edit_muscles = st.multiselect(
                            "Muscles", muscles_list, musc_list, key=f"edit_mus_{name}"
                        )
                        if st.button("Update", key=f"upd_eq_{name}"):
                            try:
                                self.equipment.update(name, edit_type, edit_muscles, edit_name)
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
            if muscles:
                col1, col2 = st.columns(2)
                with col1:
                    m1 = st.selectbox("Muscle 1", muscles, key="link_m1")
                with col2:
                    m2 = st.selectbox("Muscle 2", muscles, key="link_m2")
                if st.button("Link Muscles"):
                    self.muscles_repo.link(m1, m2)
                    st.success("Linked")

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
            if names:
                col1, col2 = st.columns(2)
                with col1:
                    e1 = st.selectbox("Exercise 1", names, key="link_ex1")
                with col2:
                    e2 = st.selectbox("Exercise 2", names, key="link_ex2")
                if st.button("Link Exercises"):
                    self.exercise_names_repo.link(e1, e2)
                    st.success("Linked")

            new_ex = st.text_input("New Exercise Name", key="new_ex_alias")
            link_ex = st.selectbox("Link To", names, key="link_ex_to")
            if st.button("Add Exercise Alias"):
                if new_ex:
                    self.exercise_names_repo.add_alias(new_ex, link_ex)
                    st.success("Alias added")
                else:
                    st.warning("Name required")


if __name__ == "__main__":
    GymApp().run()

