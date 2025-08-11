from .exercise_prescription import ExercisePrescription

class ExerciseProgressEstimator(ExercisePrescription):
    """Utility for forecasting 1RM progression using prescription logic."""

    @classmethod
    def predict_progress(
        cls,
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        rpe_scores: list[int],
        weeks: int,
        workouts_per_week: int,
        *,
        body_weight: float,
        months_active: float,
        workouts_per_month: float,
    ) -> list[dict]:
        """Predict future 1RM values for several weeks."""

        w_hist = list(weights)
        r_hist = list(reps)
        t_hist = list(timestamps)
        rpe_hist = list(rpe_scores)
        current_time = t_hist[-1] if t_hist else 0.0
        forecast: list[dict] = []

        for week in range(1, weeks + 1):
            for _ in range(workouts_per_week):
                presc = cls.exercise_prescription(
                    w_hist,
                    r_hist,
                    t_hist,
                    rpe_hist,
                    body_weight=body_weight,
                    months_active=months_active,
                    workouts_per_month=workouts_per_month,
                )
                data = presc["prescription"][0]
                current_time += 1
                t_hist.append(current_time)
                w_hist.append(float(data["weight"]))
                r_hist.append(int(data["reps"]))
                rpe_hist.append(int(round(data["target_rpe"])))

            est = cls._current_1rm(w_hist, r_hist)
            forecast.append({"week": week, "est_1rm": round(est, 2)})

        return forecast
