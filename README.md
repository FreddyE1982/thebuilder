# The Builder Workout Tracker

The Builder is a full featured workout planner, logger and analytics platform built with Streamlit and FastAPI. All data is stored in a local SQLite database and configuration values are mirrored in a `settings.yaml` file.

## Features

- Fully responsive Streamlit interface with automatic layout detection for desktop and mobile devices, including orientation-aware layouts.
- Improved metric grid and navigation styling ensure full compatibility on small screens.
- Additional grid breakpoints enhance layout on very large and ultra-wide displays.
- Mobile layouts stack columns vertically, resize charts and provide horizontal scrolling for wide tables.
- Desktop mode features a sticky top navigation bar for quick access to main tabs.
- REST API exposing every action used by the GUI.
- Log workouts with training type, exercises and detailed sets. Each set stores reps, weight, RPE and timestamps.
- Plan future workouts, duplicate plans and convert them to logged sessions.
- Duplicate logged workouts via `/workouts/{id}/duplicate` including all sets.
- Manage equipment and muscle mappings. Custom equipment can be added and linked to muscles.
- Maintain an exercise catalog with primary/secondary muscles and available equipment.
- Mark favorite exercises for quick access in the library.
- Mark favorite workout templates for faster planning.
- Create aliases for muscles and exercise names so queries treat them as the same entry.
- Extensive statistics including daily volume, progression forecasts, stress metrics, readiness scores and personal records.
- Interactive personal record tracker available in the Progress tab.
- Optional gamification awarding points for completed sets.
- Machine learning models for RPE, volume, readiness and progress predictions. The RPE predictor now uses reps, weight and previous effort for multi‑modal estimation. Training and prediction can be toggled in the settings. Reinforcement learning dynamically adjusts exercise goals and an LSTM model tracks long‑term adaptation. Injury risk analytics provide preventive insights.
- Model confidence scores are logged and fused with algorithmic recommendations using weighted averaging for transparent prescriptions.
- Multi-modal adaptation index fuses stress, fatigue and variability metrics using a deep learning model.
- Utilities such as pyramid strength tests and warm‑up weight suggestions.
- All settings can be changed in the UI or by editing `settings.yaml` and remain synchronized.
- Log daily wellness metrics like calories, sleep and stress and view summary statistics.
- Calculate average rest times between sets via `/stats/rest_times`.
- Measure total session duration via `/stats/session_duration` and view results in the Reports tab.
- Calculate total time under tension per workout via `/stats/time_under_tension`.
- Assess workout variety with `/stats/exercise_diversity` and charts in the Reports tab.
- Analyze training intensity zones with `/stats/intensity_distribution` displayed under Exercise Stats.
- View velocity history per exercise with `/stats/velocity_history` and charts in the Stats tab.
- View power output history per exercise with `/stats/power_history`.
- View relative power (W/kg) history per exercise with `/stats/relative_power_history`.
- Summarize volume by muscle group with `/stats/muscle_group_usage`.
- Summarize workouts by location with `/stats/location_summary` and view tables in the Reports tab.
- Summarize workouts by training type with `/stats/training_type_summary`.
- Evaluate exercise frequency per week with `/stats/exercise_frequency`.
- Evaluate workout schedule consistency with `/stats/workout_consistency` displayed in Reports.
- Analyze week-over-week volume change with `/stats/weekly_volume_change` displayed in the Reports tab.
- Track weekly workout streaks with `/stats/weekly_streak` and view metrics in Progress Summary.
- Track body weight over time using `/body_weight` endpoints and `/stats/weight_stats`.
- Forecast future body weight trends with `/stats/weight_forecast`.
- View weight history, BMI charts and forecasts in the Progress tab's new "Body Weight" section.
- Review workout ratings via `/stats/rating_history` and `/stats/rating_stats`.
- Analyze heart rate zone distribution with `/stats/heart_rate_zones`.

## Database Schema

All data is stored in a local SQLite database. The key tables are:

| Table | Purpose |
|-------|---------|
| `workouts` | Logged workout sessions |
| `exercises` | Exercises within a workout |
| `sets` | Individual sets for an exercise |
| `planned_workouts` | Future planned sessions |
| `planned_exercises` | Exercises in a planned workout |
| `planned_sets` | Planned sets for a planned exercise |
| `workout_templates` | Saved workout templates |
| `template_exercises` | Exercises belonging to templates |
| `template_sets` | Sets for a template exercise |
| `equipment` | Available equipment items |
| `muscles` | Muscle names and aliases |
| `exercise_catalog` | Master list of exercises |
| `body_weight_logs` | Logged body weight entries |
| `wellness_logs` | Daily wellness metrics |
| `heart_rate_logs` | Heart rate measurements |
| `tags` | User-defined workout tags |
| `ml_models` | Stored machine learning model states |
| `ml_logs` | Predictions with confidence values |


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

### Environment Variables

The following variables control runtime paths:

| Variable  | Description                      | Default        |
|-----------|----------------------------------|----------------|
| `DB_PATH` | Path to the SQLite database file | `workout.db`   |
| `DB_URL`  | Optional PostgreSQL connection URL | *(unset)* |
| `YAML_PATH` | Path to the settings YAML       | `settings.yaml`|
| `TEST_MODE` | Enable simplified test behaviour | `0` |

### Deleting Data

Send the parameter `confirmation=Yes, I confirm` to any of the endpoints below:

- `POST /settings/delete_all` – remove all logged and planned workouts
- `POST /settings/delete_logged` – remove only logged workouts
- `POST /settings/delete_planned` – remove only planned workouts

## Testing

After installing the requirements you can run the automated tests with:

```bash
pytest --cov=.
```

The tests exercise the entire REST API including machine learning features and a long‑term usage simulation covering six months of activity.
Machine learning predictions may vary slightly; tests only validate value ranges.

## Customizing CSS

Custom styling for responsive layouts can be adjusted in `streamlit_app.py` inside the `_inject_responsive_css` function. Edit the CSS rules there to override fonts, colors or layout tweaks. The function is called on every page load so changes apply immediately when the app reloads.

## Docker Compose

For local development you can run the API and Streamlit app using Docker Compose:

```bash
docker-compose up
```

This builds a Python image, installs the requirements and starts both the FastAPI
backend on port `8000` and the Streamlit frontend on port `8501`.

## Command Line Tools

Several helper commands are available via `cli.py`.

- `export`/`backup`/`restore` manage database files and workout exports.
- `import_strava --csv path --db workout.db` imports workouts from a Strava CSV export.

### ML Model Plugins

Custom machine learning models can be added by placing Python modules in a `plugins` directory. Each module must define a class inheriting from `ml_plugins.MLModelPlugin` and implement `register(service)` to extend the ML service. Plugins are loaded automatically on startup.

