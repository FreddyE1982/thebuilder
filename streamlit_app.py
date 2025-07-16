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
    GamificationRepository,
)
from planner_service import PlannerService
from recommendation_service import RecommendationService
from stats_service import StatisticsService
from gamification_service import GamificationService


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(self) -> None:
        self.settings_repo = SettingsRepository()
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
        self.equipment = EquipmentRepository()
        self.exercise_catalog = ExerciseCatalogRepository()
        self.muscles_repo = MuscleRepository()
        self.exercise_names_repo = ExerciseNameRepository()
        self.pyramid_tests = PyramidTestRepository()
        self.pyramid_entries = PyramidEntryRepository()
        self.game_repo = GamificationRepository()
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings_repo,
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
            self.exercise_names_repo,
            self.settings_repo,
            self.gamification,
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
        if "pyramid_inputs" not in st.session_state:
            st.session_state.pyramid_inputs = [0.0]

    def _create_sidebar(self) -> None:
        st.sidebar.header("Quick Actions")
        if st.sidebar.button("New Workout"):
            wid = self.workouts.create(
                datetime.date.today().isoformat(),
                "strength",
            )
            st.session_state.selected_workout = wid
            st.sidebar.success(f"Created workout {wid}")
        with st.sidebar.expander("Help & About"):
            if st.button("Show Help", key="help_btn"):
                self._help_dialog()

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
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Workouts", stats["workouts"])
            m2.metric("Volume", stats["volume"])
            m3.metric("Avg RPE", stats["avg_rpe"])
            m4.metric("Exercises", stats["exercises"])
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
            top_ex = self.stats.exercise_summary(None, start.isoformat(), end.isoformat())
            top_ex.sort(key=lambda x: x["volume"], reverse=True)
            if top_ex:
                with st.expander("Top Exercises", expanded=False):
                    st.table(top_ex[:5])

    def run(self) -> None:
        st.title("Workout Logger")
        self._create_sidebar()
        self._refresh()
        (
            log_tab,
            plan_tab,
            library_tab,
            history_tab,
            stats_tab,
            tests_tab,
            settings_tab,
        ) = st.tabs(
            [
                "Log",
                "Plan",
                "Library",
                "History",
                "Statistics",
                "Tests",
                "Settings",
            ]
        )
        with log_tab:
            self._log_tab()
        with plan_tab:
            self._plan_tab()
        with library_tab:
            self._library_tab()
        with history_tab:
            self._history_tab()
        with stats_tab:
            self._dashboard_tab()
            self._stats_tab()
            self._insights_tab()
            self._reports_tab()
        with tests_tab:
            self._tests_tab()
        with settings_tab:
            self._settings_tab()

    def _log_tab(self) -> None:
        plans = self.planned_workouts.fetch_all()
        options = {str(p[0]): p for p in plans}
        if options:
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
                        "Select Workout",
                        list(options.keys()),
                        format_func=lambda x: options[x][1],
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
                if st.button("Add Exercise"):
                    if ex_name and eq:
                        self.exercises.add(workout_id, ex_name, eq)
                    else:
                        st.warning("Exercise and equipment required")
            with st.expander("Logged Exercises", expanded=True):
                exercises = self.exercises.fetch_for_workout(workout_id)
                for ex_id, name, eq_name in exercises:
                    self._exercise_card(ex_id, name, eq_name)
            summary = self.sets.workout_summary(workout_id)
            with st.expander("Workout Summary", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Volume", summary["volume"])
                col2.metric("Sets", summary["sets"])
                col3.metric("Avg RPE", summary["avg_rpe"])

    def _exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str]
    ) -> None:
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
            with st.expander("Sets", expanded=True):
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
                        self._confirm_delete_set(set_id)
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
        last = self.sets.fetch_for_exercise(exercise_id)
        if last:
            if st.button("Copy Last Set", key=f"copy_{exercise_id}"):
                l = last[-1]
                st.session_state[f"new_reps_{exercise_id}"] = int(l[1])
                st.session_state[f"new_weight_{exercise_id}"] = float(l[2])
                st.session_state[f"new_rpe_{exercise_id}"] = int(l[3])
        if st.button("Add Set", key=f"add_set_{exercise_id}"):
            self.sets.add(exercise_id, int(reps), float(weight), int(rpe))
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
                    self.gamification.record_set(
                        exercise_id, reps_i, weight_f, rpe_i
                    )
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
                    pid = self.planned_workouts.create(
                        plan_date.isoformat(), plan_type
                    )
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
                                self.planner.duplicate_plan(
                                    pid, dup_date.isoformat()
                                )
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
        sel_type = st.selectbox("Type", types, key="lib_eq_type")
        prefix = st.text_input("Name Contains", key="lib_eq_prefix")
        mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
        names = self.equipment.fetch_names(
            sel_type or None,
            prefix or None,
            mus_filter or None,
        )
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
        for wid, date, _s, _e, training_type in workouts:
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
            for ex_id, name, eq in exercises:
                sets = self.sets.fetch_for_exercise(ex_id)
                header = name if not eq else f"{name} ({eq})"
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
                st.line_chart({"TSB": [d["tsb"] for d in tsb]}, x=[d["date"] for d in tsb])

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
                end = st.date_input(
                    "End", datetime.date.today(), key="insights_end"
                )
        if ex_choice:
            insights = self.stats.progress_insights(
                ex_choice, start.isoformat(), end.isoformat()
            )
            prog = self.stats.progression(
                ex_choice, start.isoformat(), end.isoformat()
            )
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

    def _reports_tab(self) -> None:
        st.header("Reports")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start", datetime.date.today() - datetime.timedelta(days=30), key="rep_start"
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

        gen_tab, eq_tab, mus_tab, ex_tab, cust_tab = st.tabs(
            [
                "General",
                "Equipment",
                "Muscles",
                "Exercise Aliases",
                "Custom Exercises",
            ]
        )

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
            theme_opt = st.selectbox(
                "Theme",
                ["light", "dark"],
                index=["light", "dark"].index(self.theme),
            )
            game_enabled = st.checkbox(
                "Enable Gamification",
                value=self.gamification.is_enabled(),
            )
            st.metric("Total Points", self.gamification.total_points())
            if st.button("Save General Settings"):
                self.settings_repo.set_float("body_weight", bw)
                self.settings_repo.set_float("months_active", ma)
                self.settings_repo.set_text("theme", theme_opt)
                self.theme = theme_opt
                self._apply_theme()
                self.gamification.enable(game_enabled)
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


if __name__ == "__main__":
    GymApp().run()
