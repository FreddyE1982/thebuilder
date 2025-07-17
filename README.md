# The Builder Workout Tracker

The Builder is a full featured workout planner, logger and analytics platform built with Streamlit and FastAPI. All data is stored in a local SQLite database and configuration values are mirrored in a `settings.yaml` file.

## Features

- Responsive Streamlit interface for desktop and mobile devices.
- REST API exposing every action used by the GUI.
- Log workouts with training type, exercises and detailed sets. Each set stores reps, weight, RPE and timestamps.
- Plan future workouts, duplicate plans and convert them to logged sessions.
- Manage equipment and muscle mappings. Custom equipment can be added and linked to muscles.
- Maintain an exercise catalog with primary/secondary muscles and available equipment.
- Create aliases for muscles and exercise names so queries treat them as the same entry.
- Extensive statistics including daily volume, progression forecasts, stress metrics, readiness scores and personal records.
- Optional gamification awarding points for completed sets.
- Machine learning models for RPE, volume, readiness and progress predictions. Training and prediction can be toggled in the settings.
- Utilities such as pyramid strength tests and warm‑up weight suggestions.
- All settings can be changed in the UI or by editing `settings.yaml` and remain synchronized.

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

The tests exercise the entire REST API including machine learning features and a long‑term usage simulation.
