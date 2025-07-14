# Workout Logger

This repository contains a Streamlit application for tracking gym workouts. Every workout is stored in an SQLite database. The application allows you to:

- Create new workouts with the current date.
- Add and remove exercises for a workout.
- Add, edit, and delete sets for each exercise.
- Record the RPE (0-10) for each set.
- Delete logged and planned workouts through the Settings tab or REST API.

## Requirements

- Python 3.9+
- Streamlit
- FastAPI
- Uvicorn

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Running the App

```bash
streamlit run streamlit_app.py
```

## Running the REST API

```bash
uvicorn rest_api:app --reload
```

### Deletion Endpoints

Use the following endpoints with the parameter `confirmation=Yes, I confirm` to
remove data:

- `POST /settings/delete_all` – remove all logged and planned workouts
- `POST /settings/delete_logged` – remove all logged workouts only
- `POST /settings/delete_planned` – remove all planned workouts only
