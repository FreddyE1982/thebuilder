import datetime
import streamlit as st
from db import WorkoutRepository, ExerciseRepository, SetRepository


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(self) -> None:
        self.workouts = WorkoutRepository()
        self.exercises = ExerciseRepository()
        self.sets = SetRepository()
        self._state_init()

    def _state_init(self) -> None:
        if "selected_workout" not in st.session_state:
            st.session_state.selected_workout = None
        if "exercise_inputs" not in st.session_state:
            st.session_state.exercise_inputs = {}

    def run(self) -> None:
        st.title("Workout Logger")
        self._workout_section()
        if st.session_state.selected_workout:
            self._exercise_section()

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
            for set_id, reps, weight in sets:
                cols = st.columns(4)
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
                if cols[3].button("Delete", key=f"del_{set_id}"):
                    self.sets.remove(set_id)
                    continue
                if cols[3].button("Update", key=f"upd_{set_id}"):
                    self.sets.update(set_id, int(reps_val), float(weight_val))
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
        if st.button("Add Set", key=f"add_set_{exercise_id}"):
            self.sets.add(exercise_id, int(reps), float(weight))
            st.session_state.pop(f"new_reps_{exercise_id}", None)
            st.session_state.pop(f"new_weight_{exercise_id}", None)


if __name__ == "__main__":
    GymApp().run()

