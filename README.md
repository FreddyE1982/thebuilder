# Workout Logger

This repository contains a Streamlit application for tracking gym workouts. Every workout is stored in an SQLite database. The application allows you to:

- Create new workouts with the current date.
- Add and remove exercises for a workout.
- Add, edit, and delete sets for each exercise.
- Record the RPE (0-10) for each set.

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
