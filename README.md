# The Builder Workout Tracker

The Builder is a full featured workout planner, logger and analytics platform built with Streamlit and FastAPI. All data is stored in a local SQLite database and configuration values are mirrored in a `settings.yaml` file.

## Features

- Fully responsive Streamlit interface with automatic layout detection for desktop and mobile devices, including orientation-aware layouts.
- Mobile layouts stack columns vertically, resize charts and provide horizontal scrolling for wide tables.
- REST API exposing every action used by the GUI.
- Log workouts with training type, exercises and detailed sets. Each set stores reps, weight, RPE and timestamps.
- Plan future workouts, duplicate plans and convert them to logged sessions.
- Manage equipment and muscle mappings. Custom equipment can be added and linked to muscles.
- Maintain an exercise catalog with primary/secondary muscles and available equipment.
- Mark favorite exercises for quick access in the library.
- Mark favorite workout templates for faster planning.
- Create aliases for muscles and exercise names so queries treat them as the same entry.
- Extensive statistics including daily volume, progression forecasts, stress metrics, readiness scores and personal records.
- Optional gamification awarding points for completed sets.
- Machine learning models for RPE, volume, readiness and progress predictions. The RPE predictor now uses reps, weight and previous effort for multi‑modal estimation. Training and prediction can be toggled in the settings. Reinforcement learning dynamically adjusts exercise goals and an LSTM model tracks long‑term adaptation. Injury risk analytics provide preventive insights.
- Model confidence scores are logged and fused with algorithmic recommendations using weighted averaging for transparent prescriptions.
- Multi-modal adaptation index fuses stress, fatigue and variability metrics using a deep learning model.
- Utilities such as pyramid strength tests and warm‑up weight suggestions.
- All settings can be changed in the UI or by editing `settings.yaml` and remain synchronized.
- Log daily wellness metrics like calories, sleep and stress and view summary statistics.
- Calculate average rest times between sets via `/stats/rest_times`.
- Analyze training intensity zones with `/stats/intensity_distribution`.
- Summarize volume by muscle group with `/stats/muscle_group_usage`.
- Evaluate exercise frequency per week with `/stats/exercise_frequency`.
- Track body weight over time using `/body_weight` endpoints and `/stats/weight_stats`.
- Forecast future body weight trends with `/stats/weight_forecast`.
- View weight history, BMI charts and forecasts in the Progress tab's new "Body Weight" section.
- Review workout ratings via `/stats/rating_history` and `/stats/rating_stats`.

## Installation

Python 3.9+ is required. Install the dependencies with:

```bash
pip install -r requirements.txt
```

## Running

### Streamlit UI

```bash
streamlit run streamlit_app.py
```

### REST API

```bash
uvicorn rest_api:app --reload
```

Data is stored in `workout.db` and settings in `settings.yaml` in the current directory.

### Deleting Data

Send the parameter `confirmation=Yes, I confirm` to any of the endpoints below:

- `POST /settings/delete_all` – remove all logged and planned workouts
- `POST /settings/delete_logged` – remove only logged workouts
- `POST /settings/delete_planned` – remove only planned workouts

## Testing

After installing the requirements you can run the automated tests with:

```bash
pytest -q
```

The tests exercise the entire REST API including machine learning features and a long‑term usage simulation covering six months of activity.
Machine learning predictions may vary slightly; tests only validate value ranges.
