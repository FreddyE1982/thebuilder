import datetime
import streamlit as st
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
)
from planner_service import PlannerService


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(self) -> None:
        self.workouts = WorkoutRepository()
        self.exercises = ExerciseRepository()
        self.sets = SetRepository()
        self.planned_workouts = PlannedWorkoutRepository()
        self.planned_exercises = PlannedExerciseRepository()
        self.planned_sets = PlannedSetRepository()
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
        )
        self._state_init()

    def _state_init(self) -> None:
        if "selected_workout" not in st.session_state:
            st.session_state.selected_workout = None
        if "exercise_inputs" not in st.session_state:
            st.session_state.exercise_inputs = {}
        if "selected_planned_workout" not in st.session_state:
            st.session_state.selected_planned_workout = None

    def run(self) -> None:
        st.title("Workout Logger")
        log_tab, plan_tab = st.tabs(["Log", "Plan"])
        with log_tab:
            self._log_tab()
        with plan_tab:
            self._plan_tab()

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
        if st.button("New Workout"):
            new_id = self.workouts.create(datetime.date.today().isoformat())
            st.session_state.selected_workout = new_id
        workouts = self.workouts.fetch_all_workouts()
        options = {str(w[0]): w for w in workouts}
        if options:
            selected = st.selectbox(
                "Select Workout", list(options.keys()),
                format_func=lambda x: options[x][1]
            )
            st.session_state.selected_workout = int(selected)

    def _exercise_section(self) -> None:
        st.header("Exercises")
        workout_id = st.session_state.selected_workout
        new_name = st.text_input("New Exercise Name", key="new_exercise")
        if st.button("Add Exercise") and new_name:
            self.exercises.add(workout_id, new_name)
            st.session_state.exercise_inputs.pop("new_exercise", None)
        exercises = self.exercises.fetch_for_workout(workout_id)
        for ex_id, name in exercises:
            self._exercise_card(ex_id, name)

    def _exercise_card(self, exercise_id: int, name: str) -> None:
        sets = self.sets.fetch_for_exercise(exercise_id)
        expander = st.expander(name)
        with expander:
            if st.button("Remove Exercise", key=f"remove_ex_{exercise_id}"):
                self.exercises.remove(exercise_id)
                return
            for set_id, reps, weight, rpe in sets:
                cols = st.columns(5)
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
                if cols[4].button("Delete", key=f"del_{set_id}"):
                    self.sets.remove(set_id)
                    continue
                if cols[4].button("Update", key=f"upd_{set_id}"):
                    self.sets.update(
                        set_id, int(reps_val), float(weight_val), int(rpe_val)
                    )
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

    def _planned_workout_section(self) -> None:
        st.header("Planned Workouts")
        plan_date = st.date_input("Plan Date", datetime.date.today(), key="plan_date")
        if st.button("New Planned Workout"):
            pid = self.planned_workouts.create(plan_date.isoformat())
            st.session_state.selected_planned_workout = pid
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
        new_name = st.text_input("New Planned Exercise", key="new_plan_ex")
        if st.button("Add Planned Exercise") and new_name:
            self.planned_exercises.add(workout_id, new_name)
            st.session_state.pop("new_plan_ex", None)
        exercises = self.planned_exercises.fetch_for_workout(workout_id)
        for ex_id, name in exercises:
            self._planned_exercise_card(ex_id, name)

    def _planned_exercise_card(self, exercise_id: int, name: str) -> None:
        sets = self.planned_sets.fetch_for_exercise(exercise_id)
        expander = st.expander(name)
        with expander:
            if st.button("Remove Planned Exercise", key=f"rem_plan_ex_{exercise_id}"):
                self.planned_exercises.remove(exercise_id)
                return
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


if __name__ == "__main__":
    GymApp().run()

