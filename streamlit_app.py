import datetime
import pandas as pd
from contextlib import contextmanager
from typing import Optional, Generator, Callable
import streamlit as st
import altair as alt
from altair.utils.deprecation import AltairDeprecationWarning
import warnings
warnings.filterwarnings("ignore", category=AltairDeprecationWarning)
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    TemplateWorkoutRepository,
    TemplateExerciseRepository,
    TemplateSetRepository,
    EquipmentRepository,
    ExerciseCatalogRepository,
    MuscleRepository,
    ExerciseNameRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
    GamificationRepository,
    MLModelRepository,
    MLLogRepository,
    BodyWeightRepository,
    WellnessRepository,
    FavoriteExerciseRepository,
    FavoriteTemplateRepository,
    FavoriteWorkoutRepository,
    TagRepository,
    GoalRepository,
)
from planner_service import PlannerService
from recommendation_service import RecommendationService
from stats_service import StatisticsService
from gamification_service import GamificationService
from ml_service import (
    PerformanceModelService,
    VolumeModelService,
    ReadinessModelService,
    ProgressModelService,
)
from tools import MathTools


class GymApp:
    """Streamlit application for workout logging."""

    def __init__(
        self, db_path: str = "workout.db", yaml_path: str = "settings.yaml"
    ) -> None:
        if hasattr(alt, "theme") or hasattr(alt, "themes"):

            @contextmanager
            def _noop_theme(
                name: str | None = None, **_: str
            ) -> Generator[None, None, None]:
                yield

            if hasattr(alt, "theme") and hasattr(alt.theme, "enable"):
                alt.theme.enable = _noop_theme
            if hasattr(alt, "themes") and hasattr(alt.themes, "enable"):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", AltairDeprecationWarning)
                    alt.themes.enable = _noop_theme
        self.settings_repo = SettingsRepository(db_path, yaml_path)
        self.theme = self.settings_repo.get_text("theme", "light")
        self._configure_page()
        self._inject_responsive_css()
        self._apply_theme()
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.planned_workouts = PlannedWorkoutRepository(db_path)
        self.planned_exercises = PlannedExerciseRepository(db_path)
        self.planned_sets = PlannedSetRepository(db_path)
        self.template_workouts = TemplateWorkoutRepository(db_path)
        self.template_exercises = TemplateExerciseRepository(db_path)
        self.template_sets = TemplateSetRepository(db_path)
        self.equipment = EquipmentRepository(db_path)
        self.exercise_catalog = ExerciseCatalogRepository(db_path)
        self.muscles_repo = MuscleRepository(db_path)
        self.exercise_names_repo = ExerciseNameRepository(db_path)
        self.favorites_repo = FavoriteExerciseRepository(db_path)
        self.favorite_templates_repo = FavoriteTemplateRepository(db_path)
        self.favorite_workouts_repo = FavoriteWorkoutRepository(db_path)
        self.tags_repo = TagRepository(db_path)
        self.goals_repo = GoalRepository(db_path)
        self.pyramid_tests = PyramidTestRepository(db_path)
        self.pyramid_entries = PyramidEntryRepository(db_path)
        self.game_repo = GamificationRepository(db_path)
        self.ml_models = MLModelRepository(db_path)
        self.ml_logs = MLLogRepository(db_path)
        self.body_weights_repo = BodyWeightRepository(db_path)
        self.wellness_repo = WellnessRepository(db_path)
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings_repo,
        )
        self.ml_service = PerformanceModelService(
            self.ml_models,
            self.exercise_names_repo,
            self.ml_logs,
        )
        self.volume_model = VolumeModelService(self.ml_models)
        self.readiness_model = ReadinessModelService(self.ml_models)
        self.progress_model = ProgressModelService(self.ml_models)
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
            self.gamification,
            self.template_workouts,
            self.template_exercises,
            self.template_sets,
        )
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
            self.gamification,
            self.ml_service,
            body_weight_repo=self.body_weights_repo,
        )
        self.stats = StatisticsService(
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
            self.volume_model,
            self.readiness_model,
            self.progress_model,
            None,
            None,
            self.body_weights_repo,
            self.equipment,
            self.wellness_repo,
        )
        self._state_init()

    def _refresh(self) -> None:
        """Reload the application state."""
        if st.button("Refresh"):
            st.rerun()

    def _configure_page(self) -> None:
        if st.session_state.get("layout_set"):
            return
        params = st.query_params
        mode = params.get("mode")
        if mode is None:
            st.components.v1.html(
                """
                <script>
                const mode = Math.min(window.innerWidth, window.innerHeight) < 768 ? 'mobile' : 'desktop';
                const params = new URLSearchParams(window.location.search);
                params.set('mode', mode);
                window.location.search = params.toString();
                </script>
                """,
                height=0,
            )
            mode = "desktop"
        layout = "centered" if mode == "mobile" else "wide"
        st.set_page_config(page_title="Workout Logger", layout=layout)
        st.markdown(
            "<meta name='viewport' content='width=device-width, height=device-height, initial-scale=1, shrink-to-fit=no, viewport-fit=cover'>",
            unsafe_allow_html=True,
        )
        st.session_state.layout_set = True
        st.session_state.is_mobile = mode == "mobile"
        st.components.v1.html(
            """
            <script>
            function setMode() {
                const mode = Math.min(window.innerWidth, window.innerHeight) < 768 ? 'mobile' : 'desktop';
                const params = new URLSearchParams(window.location.search);
                const cur = params.get('mode');
                if (mode !== cur) {
                    params.set('mode', mode);
                    window.location.search = params.toString();
                }
            }
            function setVh() {
                const vh = (window.visualViewport ? window.visualViewport.height : window.innerHeight) * 0.01;
                document.documentElement.style.setProperty('--vh', `${vh}px`);
            }
            function setSafeArea() {
                document.documentElement.style.setProperty('--safe-bottom', 'env(safe-area-inset-bottom)');
            }
            function setHeaderHeight() {
                const nav = document.querySelector('nav.top-nav');
                const h = nav ? nav.offsetHeight : 0;
                document.documentElement.style.setProperty('--header-height', `${h}px`);
            }
            function toggleScrollTopButton() {
                const btn = document.querySelector('.scroll-top');
                if (btn) {
                    btn.style.display = window.pageYOffset > window.innerHeight * 0.2 ? 'flex' : 'none';
                }
            }
            function handleResize() {
                setMode();
                setVh();
                setSafeArea();
                setHeaderHeight();
                toggleScrollTopButton();
            }
            window.addEventListener('resize', handleResize);
            window.addEventListener('orientationchange', handleResize);
            if (window.visualViewport) {
                window.visualViewport.addEventListener('resize', handleResize);
            }
            window.addEventListener('scroll', toggleScrollTopButton);
            window.addEventListener('DOMContentLoaded', handleResize);
            window.addEventListener('load', handleResize);
            handleResize();
            </script>
            """,
            height=0,
        )

    def _inject_responsive_css(self) -> None:
        st.markdown(
            """
            <style>
            :root {
                --section-bg: #fff;
                --safe-bottom: 0px;
            }
            html, body {
                max-width: 100%;
                overflow-x: hidden;
                overflow-y: auto;
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                scroll-behavior: smooth;
                scroll-padding-top: var(--header-height, 0);
                min-height: 100dvh;
                min-height: calc(var(--vh, 1vh) * 100);
                display: flex;
                flex-direction: column;
                overscroll-behavior-y: contain;
            }
            .page-wrapper {
                display: flex;
                flex-direction: column;
                min-height: 100dvh;
                min-height: calc(var(--vh, 1vh) * 100);
                padding-bottom: var(--safe-bottom);
            }
            .header-wrapper {
                width: 100%;
            }
            .header-inner {
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 0.5rem;
                padding: 0 0.5rem;
            }
            .content-wrapper {
                display: flex;
                flex-direction: column;
                align-items: stretch;
                width: 100%;
                max-width: 1200px;
                margin: 0 auto;
                flex: 1 0 auto;
                padding: 0 1rem;
            }
            .section-wrapper {
                margin-bottom: 1.5rem;
                background: var(--section-bg);
                border-radius: 0.5rem;
                padding: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            .title-section {
                display: flex;
                align-items: center;
                flex: 1 1 auto;
                margin: 0.25rem 0;
            }
            .title-section h1 {
                margin: 0;
            }
            h1, h2, h3 {
                margin: 0;
            }
            section.main > div {
                padding-top: 0.5rem !important;
            }
            @media screen and (max-width: 768px) {
                .header-wrapper {
                    position: sticky;
                    top: 0;
                    background: #ffffff;
                    z-index: 1000;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .header-inner {
                    flex-direction: column;
                    align-items: stretch;
                }
                .content-wrapper {
                    padding: 0 0.5rem;
                }
                .section-wrapper {
                    margin-bottom: 1rem;
                    padding: 0.5rem;
                }
                div[data-testid="column"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                }
                button[kind="primary"],
                button[kind="secondary"] {
                    width: 100%;
                }
                textarea,
                div[data-baseweb="input"] input,
                div[data-baseweb="select"] {
                    width: 100% !important;
                }
                div[data-testid="metric-container"] > label {
                    font-size: 0.9rem;
                }
                div[data-testid="stTable"] table {
                    display: block;
                    overflow-x: auto;
                    white-space: nowrap;
                    width: 100%;
                }
                div[data-testid="metric-container"] > div {
                    flex-direction: column;
                    align-items: center;
                }
                body {
                    overflow-x: hidden;
                }
                canvas {
                    max-width: 100% !important;
                    height: auto !important;
                }
                div[data-testid="stTabs"] > div:first-child {
                    overflow-x: auto;
                    white-space: nowrap;
                }
                div[data-testid="stTabs"] button {
                    flex-shrink: 0;
                }
                div[data-testid="stSidebar"] {
                    width: 100% !important;
                }
                h1 {
                    font-size: 1.75rem;
                }
                h2 {
                    font-size: 1.5rem;
                }
                h3 {
                    font-size: 1.25rem;
                }
            }

            @media screen and (max-width: 1024px) {
                div[data-testid="metric-container"] > label {
                    font-size: 1rem;
                }
            }

            @media screen and (max-width: 1024px) and (orientation: landscape) {
                section.main > div {
                    padding: 0.75rem !important;
                }
                div[data-testid="column"] {
                    flex-direction: row;
                    flex-wrap: wrap;
                }
            }

            @media screen and (max-width: 768px) and (orientation: landscape) {
                .content-wrapper {
                    padding: 0.25rem;
                }
                .header-wrapper {
                    position: fixed;
                    left: 0;
                    right: 0;
                }
                section.main > div {
                    padding: 0.5rem !important;
                }
                .section-wrapper {
                    margin-bottom: 0.75rem;
                    padding: 0.25rem 0;
                }
                div[data-testid="column"] {
                    flex-direction: row;
                    flex-wrap: wrap;
                }
            }

            @media screen and (max-width: 480px) {
                .content-wrapper {
                    padding: 0.5rem 0.25rem;
                }
                section.main > div {
                    padding: 0.5rem !important;
                }
                h1 {
                    font-size: 1.5rem;
                }
                h2 {
                    font-size: 1.25rem;
                }
                h3 {
                    font-size: 1rem;
                }
            }

            @media screen and (max-width: 480px) and (orientation: landscape) {
                .content-wrapper {
                    padding: 0.25rem;
                }
                section.main > div {
                    padding: 0.25rem !important;
                }
                .section-wrapper {
                    margin-bottom: 0.5rem;
                }
                div[data-testid="column"] {
                    flex-direction: row;
                    flex-wrap: wrap;
                }
                nav.bottom-nav {
                    flex-wrap: wrap;
                }
                nav.bottom-nav button {
                    flex: 1 0 25%;
                }
                nav.bottom-nav .label {
                    display: none;
                }
            }
            @media screen and (max-width: 480px) and (orientation: portrait) {
                nav.bottom-nav {
                    grid-template-columns: repeat(4, 1fr);
                    height: 2.75rem;
                }
                nav.bottom-nav .label {
                    font-size: 0.75rem;
                }
            }
            @media screen and (max-width: 320px) and (orientation: landscape) {
                .content-wrapper {
                    padding: 0.2rem;
                }
                section.main > div {
                    padding: 0.2rem !important;
                }
                .section-wrapper {
                    margin-bottom: 0.3rem;
                }
                h1 {
                    font-size: 1.25rem;
                }
                h2 {
                    font-size: 1rem;
                }
                h3 {
                    font-size: 0.875rem;
                }
            }
            @media screen and (max-width: 320px) {
                .content-wrapper {
                    padding: 0.3rem;
                }
                section.main > div {
                    padding: 0.3rem !important;
                }
                h1 {
                    font-size: 1.2rem;
                }
                h2 {
                    font-size: 0.95rem;
                }
                h3 {
                    font-size: 0.8rem;
                }
            }
            @media screen and (max-width: 414px) and (orientation: landscape) {
                .content-wrapper {
                    padding: 0.3rem;
                }
                .section-wrapper {
                    margin-bottom: 0.5rem;
                }
                nav.bottom-nav button {
                    flex: 1 0 33%;
                }
                .metric-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            @media screen and (max-width: 768px) {
                body {
                    padding-bottom: calc(var(--safe-bottom) + 3rem);
                }
                .content-wrapper {
                    padding-bottom: 3rem;
                }
                .bottom-nav {
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    background: #ffffff;
                    border-top: 1px solid #cccccc;
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    justify-items: center;
                    padding: 0.25rem 0.5rem var(--safe-bottom);
                    gap: 0.25rem;
                    z-index: 1000;
                    height: 3rem;
                }
                .bottom-nav button {
                    flex: 1 1 auto;
                    margin: 0 0.25rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    white-space: pre-line;
                    font-size: 0.85rem;
                    touch-action: manipulation;
                }
                nav.bottom-nav .icon {
                    font-size: 1.25rem;
                    line-height: 1;
                }
                nav.bottom-nav .label {
                    font-size: 0.75rem;
                }
            }
            @media screen and (max-width: 360px) {
                nav.bottom-nav {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            @media screen and (max-width: 600px) {
                nav.bottom-nav button {
                    font-size: 0.8rem;
                }
            }
            @media screen and (max-width: 375px) and (orientation: portrait) {
                nav.bottom-nav button {
                    font-size: 0.65rem;
                }
                nav.bottom-nav .icon {
                    font-size: 1.1rem;
                }
            }
            @media screen and (max-width: 600px) and (orientation: landscape) {
                nav.bottom-nav button {
                    font-size: 0.7rem;
                }
            }
            @media screen and (max-width: 768px) and (orientation: portrait) {
                nav.bottom-nav {
                    grid-template-columns: repeat(4, 1fr);
                    justify-content: space-evenly;
                    gap: 0.5rem;
                    overflow-x: auto;
                    grid-auto-flow: column;
                    grid-auto-columns: 1fr;
                }
            }
            @media screen and (max-width: 768px) and (orientation: landscape) {
                .content-wrapper {
                    padding: 0.25rem;
                }
                .header-inner {
                    flex-direction: row;
                }
                nav.bottom-nav {
                    grid-template-columns: repeat(4, 1fr);
                    padding: 0.1rem 0.25rem var(--safe-bottom);
                    gap: 0.1rem;
                    justify-content: space-between;
                    height: 2.5rem;
                    overflow-x: auto;
                    grid-auto-flow: column;
                    grid-auto-columns: 1fr;
                }
                nav.bottom-nav button {
                    font-size: 0.75rem;
                    padding: 0.25rem;
                    flex-direction: row;
                    gap: 0.25rem;
                    touch-action: manipulation;
                }
                nav.bottom-nav .label {
                    font-size: 0.7rem;
                }
                nav.bottom-nav {
                    height: 2.25rem;
                }
                nav.bottom-nav .icon {
                    font-size: 1rem;
                }
            }
            nav.top-nav {
                position: sticky;
                top: 0;
                background: #ffffff;
                border-bottom: 1px solid #cccccc;
                display: flex;
                justify-content: space-around;
                padding: 0.25rem 0.5rem;
                z-index: 1000;
            }
            @media screen and (max-width: 768px) and (orientation: portrait) {
                nav.top-nav {
                    position: sticky;
                }
            }
            @media screen and (max-width: 768px) and (orientation: landscape) {
                nav.top-nav {
                    position: fixed;
                    left: 0;
                    right: 0;
                }
            }
            nav.top-nav button {
                flex: 1 1 auto;
                margin: 0 0.25rem;
                display: flex;
                flex-direction: column;
                align-items: center;
                white-space: pre-line;
                font-size: 0.9rem;
            }
            nav.top-nav .icon {
                font-size: 1.1rem;
                line-height: 1;
            }
            nav.top-nav .label {
                font-size: 0.9rem;
            }
            @media screen and (max-width: 375px) {
                nav.top-nav .label {
                    font-size: 0.75rem;
                }
            }
            @media screen and (min-width: 769px) {
                nav.top-nav button {
                    font-size: 1rem;
                }
                nav.top-nav .icon {
                    font-size: 1.25rem;
                }
            }
            nav.bottom-nav button,
            nav.top-nav button {
                background: transparent;
                border: none;
                width: 100%;
                user-select: none;
                touch-action: manipulation;
            }
            nav.bottom-nav {
                scroll-snap-type: x mandatory;
            }
            nav.bottom-nav button {
                scroll-snap-align: start;
            }
            button[aria-selected="true"] {
                border-bottom: 2px solid #ff4b4b;
                background: #f0f0f0;
            }
            nav.bottom-nav button:focus, nav.top-nav button:focus {
                outline: 2px solid #ff4b4b;
            }
            .metric-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
                gap: 0.5rem;
                justify-items: center;
                width: 100%;
                overflow-x: auto;
                padding: 0.25rem;
                scroll-snap-type: x mandatory;
                scrollbar-width: none;
            }
            .metric-grid > div[data-testid="metric-container"] {
                width: 100%;
            }
            .metric-card {
                background: var(--section-bg);
                border-radius: 0.5rem;
                padding: 0.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .metric-grid::-webkit-scrollbar {
                display: none;
            }
            .form-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 0.5rem;
            }
            @media screen and (max-width: 768px) {
                .metric-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
                .form-grid {
                    grid-template-columns: 1fr;
                }
            }
            @media screen and (max-width: 768px) and (orientation: landscape) {
                .metric-grid {
                    grid-template-columns: repeat(3, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            @media screen and (max-width: 480px) {
                .form-grid {
                    grid-template-columns: 1fr;
                }
            }
            @media screen and (min-width: 1025px) {
                .metric-grid {
                    grid-template-columns: repeat(4, 1fr);
                }
                .content-wrapper {
                    padding-bottom: 0;
                }
            }
            @media screen and (min-width: 1200px) {
                .content-wrapper {
                    padding: 0 2rem;
                }
                .section-wrapper {
                    padding: 1.25rem;
                }
            }
            @media screen and (min-width: 1500px) {
                .content-wrapper {
                    max-width: 1400px;
                }
            }
            @media screen and (min-width: 1500px) {
                .metric-grid {
                    grid-template-columns: repeat(5, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(3, 1fr);
                }
            }
            @media screen and (min-width: 1800px) {
                .metric-grid {
                    grid-template-columns: repeat(6, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(4, 1fr);
                }
            }
            @media screen and (min-width: 2100px) {
                .metric-grid {
                    grid-template-columns: repeat(7, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(5, 1fr);
                }
            }
            @media screen and (min-width: 2400px) {
                .metric-grid {
                    grid-template-columns: repeat(8, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(6, 1fr);
                }
            }
            @media screen and (min-width: 2700px) {
                .metric-grid {
                    grid-template-columns: repeat(9, 1fr);
                }
                .form-grid {
                    grid-template-columns: repeat(7, 1fr);
                }
            }
            button {
                padding: 0.5rem 0.75rem;
            }
            @media screen and (max-width: 768px) {
                button {
                    font-size: 0.9rem;
                }
            }
            nav.bottom-nav {
                backdrop-filter: blur(10px);
                box-shadow: 0 -2px 5px rgba(0,0,0,0.1);
                overflow-x: auto;
                white-space: nowrap;
                grid-auto-flow: column;
                grid-auto-columns: 1fr;
            }
            nav.top-nav {
                backdrop-filter: blur(10px);
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                overflow-x: auto;
            }
            @media screen and (max-width: 768px) {
                body {
                    padding-top: var(--header-height, 0);
                }
                .content-wrapper {
                    padding-top: var(--header-height, 0);
                }
            }
            .scroll-top {
                position: fixed;
                right: 0.75rem;
                bottom: calc(var(--safe-bottom) + 3.5rem);
                width: 2.25rem;
                height: 2.25rem;
                border: none;
                border-radius: 50%;
                background: #ff4b4b;
                color: #ffffff;
                font-size: 1.25rem;
                display: none;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                z-index: 1000;
            }
            @media screen and (min-width: 769px) {
                .scroll-top {
                    bottom: 1rem;
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
                :root {
                    --section-bg: #222;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <style>
                :root {
                    --section-bg: #fff;
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
        if "selected_template" not in st.session_state:
            st.session_state.selected_template = None
        if "pyramid_inputs" not in st.session_state:
            st.session_state.pyramid_inputs = [0.0]

    def _create_sidebar(self) -> None:
        st.sidebar.header("Quick Actions")
        if st.sidebar.button("New Workout"):
            wid = self.workouts.create(
                datetime.date.today().isoformat(),
                "strength",
                None,
                None,
            )
            st.session_state.selected_workout = wid
            st.sidebar.success(f"Created workout {wid}")
        if st.sidebar.button("Toggle Theme", key="toggle_theme"):
            new_theme = "dark" if self.theme == "light" else "light"
            self.settings_repo.set_text("theme", new_theme)
            self.theme = new_theme
            self._apply_theme()
            st.rerun()
        with st.sidebar.expander("Help & About"):
            if st.button("Show Help", key="help_btn"):
                self._help_dialog()
            if st.button("Show About", key="about_btn"):
                self._about_dialog()

    def _render_nav(self, container_class: str) -> None:
        """Render navigation bar."""
        labels = ["workouts", "library", "progress", "settings"]
        icons = {
            "workouts": "🏋️",
            "library": "📚",
            "progress": "📈",
            "settings": "⚙️",
        }
        mode = "mobile" if st.session_state.is_mobile else "desktop"
        html = (
            f'<nav class="{container_class}" role="tablist" aria-label="Main Navigation">'
            + "".join(
                f'<button role="tab" title="{label.title()}" '
                f'aria-label="{label.title()} Tab" '
                f'aria-selected="{str(st.session_state.get("main_tab", 0) == idx).lower()}" '
                f'{"aria-current=\"page\" " if st.session_state.get("main_tab", 0) == idx else ""}'
                f'tabindex="0" '
                f'onclick="const p=new URLSearchParams(window.location.search);'
                f"p.set('mode','{mode}');p.set('tab','{label}');"
                f'window.location.search=p.toString();"><span class="icon">{icons[label]}</span>'
                f'<span class="label">{label.title()}</span></button>'
                for idx, label in enumerate(labels)
            )
            + "</nav>"
        )
        st.markdown(html, unsafe_allow_html=True)

    def _bottom_nav(self) -> None:
        """Render bottom navigation on mobile devices."""
        if not st.session_state.is_mobile:
            return
        self._render_nav("bottom-nav")
        self._scroll_top_button()

    def _scroll_top_button(self) -> None:
        """Render a button to quickly scroll back to the top."""
        st.markdown(
            """
            <button class='scroll-top' aria-label='Back to top' onclick="window.scrollTo({top:0,behavior:'smooth'});">⬆</button>
            """,
            unsafe_allow_html=True,
        )

    def _top_nav(self) -> None:
        """Render top navigation on desktop."""
        if st.session_state.is_mobile:
            return
        self._render_nav("top-nav")

    def _switch_tab(self, label: str) -> None:
        mode = "mobile" if st.session_state.is_mobile else "desktop"
        st.query_params.update({"mode": mode, "tab": label})
        st.rerun()

    def _metric_grid(self, metrics: list[tuple[str, str]]) -> None:
        """Render metrics in a responsive grid."""
        st.markdown("<div class='metric-grid'>", unsafe_allow_html=True)
        for label, val in metrics:
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.metric(label, val)
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    def _line_chart(self, data: dict[str, list], x: list[str]) -> None:
        """Render a line chart safely even with a single data point."""
        df = pd.DataFrame({"x": x})
        for key, values in data.items():
            df[key] = values
        df = df.set_index("x")
        st.line_chart(df, use_container_width=True)

    def _bar_chart(self, data: dict[str, list], x: list[str]) -> None:
        """Render a bar chart safely even with a single data point."""
        df = pd.DataFrame({"x": x})
        for key, values in data.items():
            df[key] = values
        df = df.set_index("x")
        st.bar_chart(df, use_container_width=True)

    def _show_dialog(self, title: str, content_fn: Callable[[], None]) -> None:
        """Display a modal dialog using the decorator API."""

        @st.dialog(title)
        def _dlg() -> None:
            content_fn()

        _dlg()

    @contextmanager
    def _section(self, title: str) -> Generator[None, None, None]:
        """Context manager for a styled section."""
        st.markdown("<div class='section-wrapper'>", unsafe_allow_html=True)
        st.header(title)
        try:
            yield
        finally:
            st.markdown("</div>", unsafe_allow_html=True)

    def _start_page(self) -> None:
        """Open the page wrapper."""
        st.markdown("<div class='page-wrapper'>", unsafe_allow_html=True)

    def _open_header(self) -> None:
        """Open the header container."""
        st.markdown(
            "<header class='header-wrapper'><div class='header-inner'>",
            unsafe_allow_html=True,
        )

    def _close_header(self) -> None:
        """Close the header container."""
        st.markdown("</div></header>", unsafe_allow_html=True)

    def _end_page(self) -> None:
        """Close the page wrapper."""
        st.markdown("</div>", unsafe_allow_html=True)

    def _open_content(self) -> None:
        """Begin main content container."""
        st.markdown("<main class='content-wrapper'>", unsafe_allow_html=True)

    def _close_content(self) -> None:
        """End main content container."""
        st.markdown("</main>", unsafe_allow_html=True)

    def _help_dialog(self) -> None:
        def _content() -> None:
            st.markdown("## Workout Logger Help")
            st.markdown(
                "Use the tabs to log workouts, plan sessions, and analyze your training data."
            )
            st.markdown(
                "All data is saved to an internal database and can be managed via the settings tab."
            )
            st.button("Close")

        self._show_dialog("Help", _content)

    def _about_dialog(self) -> None:
        def _content() -> None:
            st.markdown("## About The Builder")
            st.markdown(
                "This application is a comprehensive workout planner and logger built with Streamlit and FastAPI."
            )
            st.markdown(
                "It offers a responsive interface and a complete REST API for advanced tracking, planning and analytics."
            )
            st.button("Close")

        self._show_dialog("About", _content)

    def _dashboard_tab(self) -> None:
        with self._section("Dashboard"):
            with st.expander("Filters", expanded=True):
                if st.session_state.is_mobile:
                    start = st.date_input(
                        "Start",
                        datetime.date.today() - datetime.timedelta(days=30),
                        key="dash_start",
                    )
                    end = st.date_input("End", datetime.date.today(), key="dash_end")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        start = st.date_input(
                            "Start",
                            datetime.date.today() - datetime.timedelta(days=30),
                            key="dash_start",
                        )
                    with col2:
                        end = st.date_input(
                            "End", datetime.date.today(), key="dash_end"
                        )
                if st.button("Reset", key="dash_reset"):
                    st.session_state.dash_start = (
                        datetime.date.today() - datetime.timedelta(days=30)
                    )
                    st.session_state.dash_end = datetime.date.today()
                    st.rerun()
        stats = self.stats.overview(start.isoformat(), end.isoformat())
        with st.expander("Overview Metrics", expanded=True):
            metrics = [
                ("Workouts", stats["workouts"]),
                ("Volume", stats["volume"]),
                ("Avg RPE", stats["avg_rpe"]),
                ("Exercises", stats["exercises"]),
                ("Avg Density", stats.get("avg_density", 0)),
                ("BMI", self.stats.bmi()),
            ]
            self._metric_grid(metrics)
        daily = self.stats.daily_volume(start.isoformat(), end.isoformat())
        with st.expander("Charts", expanded=True):
            if st.session_state.is_mobile:
                st.subheader("Daily Volume")
                if daily:
                    df_daily = pd.DataFrame(daily).set_index("date")
                    st.line_chart(df_daily["volume"], use_container_width=True)
                duration = self.stats.session_duration(
                    start.isoformat(), end.isoformat()
                )
                st.subheader("Session Duration")
                if duration:
                    df_dur = pd.DataFrame(duration).set_index("date")
                    st.line_chart(df_dur["duration"], use_container_width=True)
                exercises = [""] + self.exercise_names_repo.fetch_all()
                ex_choice = st.selectbox(
                    "Exercise Progression", exercises, key="dash_ex"
                )
                if ex_choice:
                    prog = self.stats.progression(
                        ex_choice, start.isoformat(), end.isoformat()
                    )
                    st.subheader("1RM Progression")
                    if prog:
                        df_prog = pd.DataFrame(prog).set_index("date")
                        st.line_chart(df_prog["est_1rm"], use_container_width=True)
            else:
                left, right = st.columns(2)
                with left:
                    st.subheader("Daily Volume")
                    if daily:
                        df_daily = pd.DataFrame(daily).set_index("date")
                        st.line_chart(df_daily["volume"], use_container_width=True)
                    exercises = [""] + self.exercise_names_repo.fetch_all()
                    ex_choice = st.selectbox(
                        "Exercise Progression", exercises, key="dash_ex"
                    )
                    if ex_choice:
                        prog = self.stats.progression(
                            ex_choice, start.isoformat(), end.isoformat()
                        )
                        st.subheader("1RM Progression")
                        if prog:
                            df_prog = pd.DataFrame(prog).set_index("date")
                            st.line_chart(df_prog["est_1rm"], use_container_width=True)
                with right:
                    duration = self.stats.session_duration(
                        start.isoformat(), end.isoformat()
                    )
                    st.subheader("Session Duration")
                    if duration:
                        df_dur = pd.DataFrame(duration).set_index("date")
                        st.line_chart(df_dur["duration"], use_container_width=True)
                    eq_stats = self.stats.equipment_usage(
                        start.isoformat(), end.isoformat()
                    )
                    if eq_stats:
                        st.subheader("Equipment Usage")
                        df_eq = pd.DataFrame(eq_stats).set_index("equipment")
                        st.bar_chart(df_eq["sets"], use_container_width=True)
            records = self.stats.personal_records(
                ex_choice if ex_choice else None,
                start.isoformat(),
                end.isoformat(),
            )
            if records:
                with st.expander("Personal Records", expanded=False):
                    st.table(records[:5])
            if not st.session_state.is_mobile:
                top_ex = self.stats.exercise_summary(
                    None, start.isoformat(), end.isoformat()
                )
                top_ex.sort(key=lambda x: x["volume"], reverse=True)
                if top_ex:
                    with st.expander("Top Exercises", expanded=False):
                        st.table(top_ex[:5])

    def run(self) -> None:
        params = st.query_params
        tab_param = params.get("tab")
        tab_map = {
            "workouts": 0,
            "library": 1,
            "progress": 2,
            "settings": 3,
        }
        if tab_param in tab_map:
            st.session_state["main_tab"] = tab_map[tab_param]
        self._start_page()
        self._open_header()
        st.markdown("<div class='title-section'>", unsafe_allow_html=True)
        st.title("Workout Logger")
        st.markdown("</div>", unsafe_allow_html=True)
        self._top_nav()
        self._close_header()
        self._create_sidebar()
        self._open_content()
        self._refresh()
        test_mode = os.environ.get("TEST_MODE") == "1"
        (
            workouts_tab,
            library_tab,
            progress_tab,
            settings_tab,
        ) = st.tabs(
            [
                "Workouts",
                "Library",
                "Progress",
                "Settings",
            ]
        )
        with workouts_tab:
            log_sub, plan_sub = st.tabs(["Log", "Plan"])
            with log_sub:
                self._log_tab()
            with plan_sub:
                self._plan_tab()
        with library_tab:
            self._library_tab()
        with progress_tab:
            if not test_mode:
                (
                    calendar_sub,
                    history_sub,
                    dash_sub,
                    stats_sub,
                    insights_sub,
                    weight_sub,
                    rep_sub,
                    risk_sub,
                    game_sub,
                    tests_sub,
                    goals_sub,
                ) = st.tabs(
                    [
                        "Calendar",
                        "History",
                        "Dashboard",
                        "Exercise Stats",
                        "Insights",
                        "Body Weight",
                        "Reports",
                        "Risk",
                        "Gamification",
                        "Tests",
                        "Goals",
                    ]
                )
                with calendar_sub:
                    self._calendar_tab()
                with history_sub:
                    self._history_tab()
                with dash_sub:
                    self._dashboard_tab()
                with stats_sub:
                    self._stats_tab()
                with insights_sub:
                    self._insights_tab()
                with weight_sub:
                    self._weight_tab()
                with rep_sub:
                    self._reports_tab()
                with risk_sub:
                    self._risk_tab()
                with game_sub:
                    self._gamification_tab()
                with tests_sub:
                    self._tests_tab()
                with goals_sub:
                    self._goals_tab()
        with settings_tab:
            self._settings_tab()
        self._close_content()
        self._bottom_nav()
        self._end_page()

    def _log_tab(self) -> None:
        plans = self.planned_workouts.fetch_all()
        options = {str(p[0]): p for p in plans}
        if options:
            with st.expander("Use Planned Workout", expanded=False):
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
        self._template_section()
        if st.session_state.get("selected_template") is not None:
            self._template_exercise_section()
        self._planned_workout_section()
        if st.session_state.selected_planned_workout:
            self._planned_exercise_section()

    def _workout_section(self) -> None:
        with self._section("Workouts"):
            training_options = ["strength", "hypertrophy", "highintensity"]
            with st.expander("Workout Management", expanded=True):
                if st.session_state.is_mobile:
                    self._create_workout_form(training_options)
                    self._existing_workout_form(training_options)
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        self._create_workout_form(training_options)
                    with col2:
                        self._existing_workout_form(training_options)

    def _create_workout_form(self, training_options: list[str]) -> None:
        with st.expander("Create New Workout"):
            with st.form("new_workout_form"):
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                new_type = st.selectbox(
                    "Training Type", training_options, key="new_workout_type"
                )
                new_location = st.text_input("Location", key="new_workout_location")
                st.markdown("</div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("New Workout")
                if submitted:
                    new_id = self.workouts.create(
                        datetime.date.today().isoformat(),
                        new_type,
                        None,
                        new_location or None,
                        None,
                    )
                    st.session_state.selected_workout = new_id

    def _existing_workout_form(self, training_options: list[str]) -> None:
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
                notes_val = detail[5] or ""
                loc_val = detail[6] or ""
                rating_val = detail[7]
                if st.session_state.is_mobile:
                    c1, c2 = st.columns(2)
                    if c1.button("Start Workout", key=f"start_workout_{selected}"):
                        self.workouts.set_start_time(
                            int(selected),
                            datetime.datetime.now().isoformat(timespec="seconds"),
                        )
                    if c2.button("Finish Workout", key=f"finish_workout_{selected}"):
                        self.workouts.set_end_time(
                            int(selected),
                            datetime.datetime.now().isoformat(timespec="seconds"),
                        )
                    type_choice = st.selectbox(
                        "Type",
                        training_options,
                        index=training_options.index(current_type),
                        key=f"type_select_{selected}",
                    )
                    if st.button("Save", key=f"save_type_{selected}"):
                        self.workouts.set_training_type(int(selected), type_choice)
                else:
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
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                notes_edit = st.text_area(
                    "Notes",
                    value=notes_val,
                    key=f"workout_notes_{selected}",
                )
                loc_edit = st.text_input(
                    "Location",
                    value=loc_val,
                    key=f"workout_location_{selected}",
                )
                rating_edit = st.slider(
                    "Rating",
                    0,
                    5,
                    value=rating_val if rating_val is not None else 0,
                    key=f"rating_{selected}",
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if st.button("Save Notes", key=f"save_notes_{selected}"):
                    self.workouts.set_note(int(selected), notes_edit)
                if st.button("Save Location", key=f"save_location_{selected}"):
                    self.workouts.set_location(int(selected), loc_edit or None)
                if st.button("Save Rating", key=f"save_rating_{selected}"):
                    self.workouts.set_rating(int(selected), int(rating_edit))
                tags_all = self.tags_repo.fetch_all()
                name_map = {n: tid for tid, n in tags_all}
                current_tags = [
                    n for _, n in self.tags_repo.fetch_for_workout(int(selected))
                ]
                tag_sel = st.multiselect(
                    "Tags",
                    [n for _, n in tags_all],
                    current_tags,
                    key=f"tags_sel_{selected}",
                )
                if st.button("Save Tags", key=f"save_tags_{selected}"):
                    ids = [name_map[n] for n in tag_sel]
                    self.tags_repo.set_tags(int(selected), ids)
                csv_data = self.sets.export_workout_csv(int(selected))
                st.download_button(
                    label="Export CSV",
                    data=csv_data,
                    file_name=f"workout_{selected}.csv",
                    mime="text/csv",
                    key=f"export_{selected}",
                )

    def _planned_workout_section(self) -> None:
        with self._section("Planned Workouts"):
            with st.expander("Plan Management", expanded=True):
                if st.session_state.is_mobile:
                    self._create_plan_form()
                    self._existing_plan_form()
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        self._create_plan_form()
                    with col2:
                        self._existing_plan_form()

    def _create_plan_form(self) -> None:
        with st.expander("Create New Plan"):
            with st.form("new_plan_form"):
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                plan_date = st.date_input(
                    "Plan Date", datetime.date.today(), key="plan_date"
                )
                training_options = ["strength", "hypertrophy", "highintensity"]
                plan_type = st.selectbox(
                    "Training Type",
                    training_options,
                    key="plan_type",
                )
                st.markdown("</div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("New Planned Workout")
                if submitted:
                    pid = self.planned_workouts.create(plan_date.isoformat(), plan_type)
                    st.session_state.selected_planned_workout = pid

    def _existing_plan_form(self) -> None:
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
                        st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                        edit_date = st.date_input(
                            "New Date",
                            datetime.date.fromisoformat(pdate),
                            key=f"plan_edit_{pid}",
                        )
                        training_options = ["strength", "hypertrophy", "highintensity"]
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
                        st.markdown("</div>", unsafe_allow_html=True)
                        if st.session_state.is_mobile:
                            if st.button("Save", key=f"save_plan_{pid}"):
                                self.planned_workouts.update_date(
                                    pid, edit_date.isoformat()
                                )
                                self.planned_workouts.set_training_type(
                                    pid, type_choice
                                )
                                st.success("Updated")
                            if st.button("Duplicate", key=f"dup_plan_{pid}"):
                                self.planner.duplicate_plan(pid, dup_date.isoformat())
                                st.success("Duplicated")
                            if st.button("Delete", key=f"del_plan_{pid}"):
                                self.planned_workouts.delete(pid)
                                st.success("Deleted")
                        else:
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
                                self.planner.duplicate_plan(pid, dup_date.isoformat())
                                st.success("Duplicated")
                            if cols[2].button("Delete", key=f"del_plan_{pid}"):
                                self.planned_workouts.delete(pid)
                                st.success("Deleted")

    def _exercise_section(self) -> None:
        with self._section("Exercises"):
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
                    note_val = st.text_input("Note", key="new_exercise_note")
                    if st.button("Add Exercise"):
                        if ex_name and eq:
                            self.exercises.add(
                                workout_id, ex_name, eq, note_val or None
                            )
                        else:
                            st.warning("Exercise and equipment required")
                with st.expander("Logged Exercises", expanded=True):
                    exercises = self.exercises.fetch_for_workout(workout_id)
                    for ex_id, name, eq_name, note in exercises:
                        self._exercise_card(ex_id, name, eq_name, note)
                summary = self.sets.workout_summary(workout_id)
                with st.expander("Workout Summary", expanded=True):
                    metrics = [
                        ("Volume", summary["volume"]),
                        ("Sets", summary["sets"]),
                        ("Avg RPE", summary["avg_rpe"]),
                    ]
                    self._metric_grid(metrics)

    def _exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str], note: Optional[str]
    ) -> None:
        sets = self.sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
        if note:
            header += f" - {note}"
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
            note_val = st.text_input(
                "Note", value=note or "", key=f"note_{exercise_id}"
            )
            if st.button("Update Note", key=f"upd_note_{exercise_id}"):
                self.exercises.update_note(exercise_id, note_val or None)
            if st.button("Clear Note", key=f"clear_note_{exercise_id}"):
                self.exercises.update_note(exercise_id, None)
                st.session_state[f"note_{exercise_id}"] = ""
            with st.expander("Sets", expanded=True):
                for set_id, reps, weight, rpe, start_time, end_time in sets:
                    detail = self.sets.fetch_detail(set_id)
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {set_id}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"reps_{set_id}",
                            )
                            weight_val = st.number_input(
                                "Weight (kg)",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"weight_{set_id}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"rpe_{set_id}",
                            )
                            note_val = st.text_input(
                                "Note",
                                value=detail.get("note") or "",
                                key=f"note_{set_id}",
                            )
                            st.write(f"{detail['diff_reps']:+}")
                            st.write(f"{detail['diff_weight']:+.1f}")
                            st.write(f"{detail['diff_rpe']:+}")
                            start_col, finish_col = st.columns(2)
                            if start_col.button("Start", key=f"start_set_{set_id}"):
                                self.sets.set_start_time(
                                    set_id,
                                    datetime.datetime.now().isoformat(
                                        timespec="seconds"
                                    ),
                                )
                            if finish_col.button("Finish", key=f"finish_set_{set_id}"):
                                self.sets.set_end_time(
                                    set_id,
                                    datetime.datetime.now().isoformat(
                                        timespec="seconds"
                                    ),
                                )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"del_{set_id}"):
                                self._confirm_delete_set(set_id)
                                continue
                            if upd_col.button("Update", key=f"upd_{set_id}"):
                                self.sets.update(
                                    set_id,
                                    int(reps_val),
                                    float(weight_val),
                                    int(rpe_val),
                                )
                                self.sets.update_note(set_id, note_val or None)
                            if start_time:
                                st.write(start_time)
                            if end_time:
                                st.write(end_time)
                    else:
                        cols = st.columns(12)
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
                        note_val = cols[4].text_input(
                            "Note",
                            value=detail.get("note") or "",
                            key=f"note_{set_id}",
                        )
                        cols[5].write(f"{detail['diff_reps']:+}")
                        cols[6].write(f"{detail['diff_weight']:+.1f}")
                        cols[7].write(f"{detail['diff_rpe']:+}")
                        if cols[8].button("Start", key=f"start_set_{set_id}"):
                            self.sets.set_start_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                        if cols[9].button("Finish", key=f"finish_set_{set_id}"):
                            self.sets.set_end_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                        if cols[10].button("Delete", key=f"del_{set_id}"):
                            self._confirm_delete_set(set_id)
                            continue
                        if cols[11].button("Update", key=f"upd_{set_id}"):
                            self.sets.update(
                                set_id, int(reps_val), float(weight_val), int(rpe_val)
                            )
                            self.sets.update_note(set_id, note_val or None)
                        if start_time:
                            cols[8].write(start_time)
                        if end_time:
                            cols[9].write(end_time)
            hist = self.stats.exercise_history(name)
            if hist:
                with st.expander("History (last 5)"):
                    st.table(hist[-5:][::-1])
                with st.expander("Weight Progress"):
                    self._line_chart(
                        {"Weight": [h["weight"] for h in hist]},
                        [h["date"] for h in hist],
                    )
                prog = self.stats.progression(name)
                if prog:
                    with st.expander("1RM Progress"):
                        self._line_chart(
                            {"1RM": [p["est_1rm"] for p in prog]},
                            [p["date"] for p in prog],
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
        note = st.text_input("Note", key=f"new_note_{exercise_id}")
        last = self.sets.fetch_for_exercise(exercise_id)
        if last:
            if st.button("Copy Last Set", key=f"copy_{exercise_id}"):
                l = last[-1]
                st.session_state[f"new_reps_{exercise_id}"] = int(l[1])
                st.session_state[f"new_weight_{exercise_id}"] = float(l[2])
                st.session_state[f"new_rpe_{exercise_id}"] = int(l[3])
        if st.button("Add Set", key=f"add_set_{exercise_id}"):
            self.sets.add(exercise_id, int(reps), float(weight), int(rpe), note or None)
            self.gamification.record_set(
                exercise_id, int(reps), float(weight), int(rpe)
            )
            st.session_state.pop(f"new_reps_{exercise_id}", None)
            st.session_state.pop(f"new_weight_{exercise_id}", None)
            st.session_state.pop(f"new_rpe_{exercise_id}", None)

    def _bulk_add_sets_dialog(self, exercise_id: int) -> None:
        def _content() -> None:
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
                    self.gamification.record_set(exercise_id, reps_i, weight_f, rpe_i)
                    added += 1
                if added:
                    st.success(f"Added {added} sets")
                st.session_state.pop(f"bulk_text_{exercise_id}", None)
            st.button("Close", key=f"bulk_close_{exercise_id}")

        self._show_dialog("Bulk Add Sets", _content)

    def _confirm_delete_set(self, set_id: int) -> None:
        def _content() -> None:
            st.write(f"Delete set {set_id}?")
            cols = st.columns(2)
            if cols[0].button("Yes", key=f"yes_{set_id}"):
                self.sets.remove(set_id)
                st.rerun()
            if cols[1].button("No", key=f"no_{set_id}"):
                st.rerun()

        self._show_dialog("Confirm Delete", _content)

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

    def _planned_exercise_section(self) -> None:
        with self._section("Planned Exercises"):
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
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {set_id}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"plan_reps_{set_id}",
                            )
                            weight_val = st.number_input(
                                "Weight (kg)",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"plan_weight_{set_id}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"plan_rpe_{set_id}",
                            )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"del_plan_set_{set_id}"):
                                self.planned_sets.remove(set_id)
                                continue
                            if upd_col.button("Update", key=f"upd_plan_set_{set_id}"):
                                self.planned_sets.update(
                                    set_id,
                                    int(reps_val),
                                    float(weight_val),
                                    int(rpe_val),
                                )
                    else:
                        cols = st.columns(6)
                        cols[0].write(f"Set {set_id}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"plan_reps_{set_id}",
                        )
                        weight_val = cols[2].number_input(
                            "Weight (kg)",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"plan_weight_{set_id}",
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"plan_rpe_{set_id}",
                        )
                        if cols[4].button("Delete", key=f"del_plan_set_{set_id}"):
                            self.planned_sets.remove(set_id)
                            continue
                        if cols[5].button("Update", key=f"upd_plan_set_{set_id}"):
                            self.planned_sets.update(
                                set_id, int(reps_val), float(weight_val), int(rpe_val)
                            )
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

    def _template_section(self) -> None:
        with self._section("Templates"):
            training_options = ["strength", "hypertrophy", "highintensity"]
            with st.expander("Template Management", expanded=True):
                favs = self.favorite_templates_repo.fetch_all()
                with st.expander("Favorite Templates", expanded=True):
                    if favs:
                        for fid in favs:
                            try:
                                _id, name, _type = self.template_workouts.fetch_detail(
                                    fid
                                )
                            except ValueError:
                                continue
                            cols = st.columns(2)
                            cols[0].write(name)
                            if cols[1].button("Remove", key=f"fav_tpl_rm_{fid}"):
                                self.favorite_templates_repo.remove(fid)
                                st.rerun()
                    else:
                        st.write("No favorites.")
                templates = {
                    str(t[0]): t[1] for t in self.template_workouts.fetch_all()
                }
                add_choice = st.selectbox(
                    "Add Favorite",
                    [""] + list(templates.keys()),
                    format_func=lambda x: "" if x == "" else templates[x],
                    key="fav_tpl_add_choice",
                )
                if st.button("Add Favorite", key="fav_tpl_add_btn") and add_choice:
                    self.favorite_templates_repo.add(int(add_choice))
                    st.rerun()
            with st.expander("Create New Template"):
                name = st.text_input("Name", key="tmpl_name")
                t_type = st.selectbox(
                    "Training Type", training_options, key="tmpl_type"
                )
                if st.button("Create Template") and name:
                    tid = self.template_workouts.create(name, t_type)
                    st.session_state.selected_template = tid
            with st.expander("Existing Templates", expanded=True):
                templates = self.template_workouts.fetch_all()
                options = {str(t[0]): t for t in templates}
                if options:
                    selected = st.selectbox(
                        "Select Template",
                        list(options.keys()),
                        format_func=lambda x: options[x][1],
                        key="select_template",
                    )
                    st.session_state.selected_template = int(selected)
                    for tid, name, t_type in templates:
                        with st.expander(f"{name} (ID {tid})", expanded=False):
                            edit_name = st.text_input(
                                "Name", value=name, key=f"tmpl_edit_name_{tid}"
                            )
                            edit_type = st.selectbox(
                                "Type",
                                training_options,
                                index=training_options.index(t_type),
                                key=f"tmpl_edit_type_{tid}",
                            )
                            plan_date = st.date_input(
                                "Create Plan Date",
                                datetime.date.today(),
                                key=f"tmpl_plan_{tid}",
                            )
                            cols = st.columns(3)
                            if cols[0].button("Save", key=f"tmpl_save_{tid}"):
                                self.template_workouts.update(tid, edit_name, edit_type)
                                st.success("Updated")
                            if cols[1].button("Plan", key=f"tmpl_plan_btn_{tid}"):
                                self.planner.create_plan_from_template(
                                    tid, plan_date.isoformat()
                                )
                                st.success("Planned")
                            if cols[2].button("Delete", key=f"tmpl_del_{tid}"):
                                self.template_workouts.delete(tid)
                                st.success("Deleted")
                else:
                    st.write("No templates.")

    def _template_exercise_section(self) -> None:
        with self._section("Template Exercises"):
            template_id = st.session_state.selected_template
            with st.expander("Exercise Management", expanded=True):
                with st.expander("Add Exercise"):
                    ex_name = self._exercise_selector(
                        "tmpl_new",
                        None,
                        st.session_state.get("tmpl_new_groups", []),
                        st.session_state.get("tmpl_new_muscles", []),
                    )
                    eq = self._equipment_selector(
                        "tmpl_new",
                        st.session_state.get("tmpl_new_muscles", []),
                    )
                    if st.button("Add Template Exercise"):
                        if ex_name and eq:
                            self.template_exercises.add(template_id, ex_name, eq)
                        else:
                            st.warning("Exercise and equipment required")
                with st.expander("Exercise List", expanded=True):
                    exercises = self.template_exercises.fetch_for_template(template_id)
                    for ex_id, name, eq in exercises:
                        self._template_exercise_card(ex_id, name, eq)

    def _template_exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str]
    ) -> None:
        sets = self.template_sets.fetch_for_exercise(exercise_id)
        header = name if not equipment else f"{name} ({equipment})"
        exp = st.expander(header)
        with exp:
            if st.button("Remove Exercise", key=f"tmpl_ex_rm_{exercise_id}"):
                self.template_exercises.remove(exercise_id)
                return
            with st.expander("Sets", expanded=True):
                for sid, reps, weight, rpe in sets:
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {sid}"):
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"tmpl_reps_{sid}",
                            )
                            weight_val = st.number_input(
                                "Weight",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"tmpl_w_{sid}",
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"tmpl_rpe_{sid}",
                            )
                            del_col, upd_col = st.columns(2)
                            if del_col.button("Delete", key=f"tmpl_del_set_{sid}"):
                                self.template_sets.remove(sid)
                                continue
                            if upd_col.button("Update", key=f"tmpl_upd_set_{sid}"):
                                self.template_sets.update(
                                    sid, int(reps_val), float(weight_val), int(rpe_val)
                                )
                    else:
                        cols = st.columns(5)
                        cols[0].write(f"Set {sid}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"tmpl_reps_{sid}",
                        )
                        weight_val = cols[2].number_input(
                            "Weight",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"tmpl_w_{sid}",
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"tmpl_rpe_{sid}",
                        )
                        if cols[4].button("Delete", key=f"tmpl_del_set_{sid}"):
                            self.template_sets.remove(sid)
                            continue
                        if cols[4].button("Update", key=f"tmpl_upd_set_{sid}"):
                            self.template_sets.update(
                                sid, int(reps_val), float(weight_val), int(rpe_val)
                            )
            with st.expander("Add Set"):
                reps = st.number_input(
                    "Reps", min_value=1, step=1, key=f"tmpl_new_reps_{exercise_id}"
                )
                weight = st.number_input(
                    "Weight", min_value=0.0, step=0.5, key=f"tmpl_new_w_{exercise_id}"
                )
                rpe = st.selectbox(
                    "RPE", options=list(range(11)), key=f"tmpl_new_rpe_{exercise_id}"
                )
                if st.button("Add Set", key=f"tmpl_add_set_{exercise_id}"):
                    self.template_sets.add(
                        exercise_id, int(reps), float(weight), int(rpe)
                    )
                    st.session_state.pop(f"tmpl_new_reps_{exercise_id}", None)
                    st.session_state.pop(f"tmpl_new_w_{exercise_id}", None)
                    st.session_state.pop(f"tmpl_new_rpe_{exercise_id}", None)

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
        if st.session_state.is_mobile:
            with st.expander("Filters", expanded=True):
                sel_type = st.selectbox("Type", types, key="lib_eq_type")
                prefix = st.text_input("Name Contains", key="lib_eq_prefix")
                mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
            names = self.equipment.fetch_names(
                sel_type or None,
                prefix or None,
                mus_filter or None,
            )
            with st.expander("Equipment List", expanded=True):
                choice = st.selectbox("Equipment", [""] + names, key="lib_eq_name")
                if choice and st.button("Details", key="lib_eq_btn"):
                    detail = self.equipment.fetch_detail(choice)
                    if detail:

                        def _content() -> None:
                            eq_type, muscs, _ = detail
                            st.markdown(f"**Type:** {eq_type}")
                            st.markdown("**Muscles:**")
                            for m in muscs:
                                st.markdown(f"- {m}")

                        self._show_dialog("Equipment Details", _content)
        else:
            f_col, l_col = st.columns([1, 2], gap="large")
            with f_col.expander("Filters", expanded=True):
                sel_type = st.selectbox("Type", types, key="lib_eq_type")
                prefix = st.text_input("Name Contains", key="lib_eq_prefix")
                mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
            names = self.equipment.fetch_names(
                sel_type or None,
                prefix or None,
                mus_filter or None,
            )
            with l_col.expander("Equipment List", expanded=True):
                choice = st.selectbox("Equipment", [""] + names, key="lib_eq_name")
                if choice and st.button("Details", key="lib_eq_btn"):
                    detail = self.equipment.fetch_detail(choice)
                    if detail:

                        def _content() -> None:
                            eq_type, muscs, _ = detail
                            st.markdown(f"**Type:** {eq_type}")
                            st.markdown("**Muscles:**")
                            for m in muscs:
                                st.markdown(f"- {m}")

                        self._show_dialog("Equipment Details", _content)

    def _exercise_catalog_library(self) -> None:
        groups = self.exercise_catalog.fetch_muscle_groups()
        muscles = self.muscles_repo.fetch_all()
        favs = self.favorites_repo.fetch_all()
        with st.expander("Favorite Exercises", expanded=True):
            if favs:
                for f in favs:
                    cols = st.columns(2)
                    cols[0].write(f)
                    if cols[1].button("Remove", key=f"fav_rm_{f}"):
                        self.favorites_repo.remove(f)
                        st.rerun()
            else:
                st.write("No favorites.")
            add_choice = st.selectbox(
                "Add Favorite",
                [""] + self.exercise_names_repo.fetch_all(),
                key="fav_add_name",
            )
            if st.button("Add Favorite", key="fav_add_btn") and add_choice:
                self.favorites_repo.add(add_choice)
                st.rerun()
        if st.session_state.is_mobile:
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
            with st.expander("Exercise List", expanded=True):
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

                        def _content() -> None:
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

                        self._show_dialog("Exercise Details", _content)
        else:
            f_col, l_col = st.columns([1, 2], gap="large")
            with f_col:
                with st.expander("Filters", expanded=True):
                    sel_groups = st.multiselect(
                        "Muscle Groups", groups, key="lib_ex_groups"
                    )
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
            with l_col:
                with st.expander("Exercise List", expanded=True):
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

                            def _content() -> None:
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

                            self._show_dialog("Exercise Details", _content)

    def _custom_exercise_management(self) -> None:
        muscles = self.muscles_repo.fetch_all()
        groups = self.exercise_catalog.fetch_muscle_groups()
        equipment_names = self.equipment.fetch_names()

        if st.session_state.is_mobile:
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
                        edit_group = st.text_input(
                            "Group", group, key=f"cust_group_{name}"
                        )
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
                        edit_other = st.text_input(
                            "Other", other, key=f"cust_oth_{name}"
                        )
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
        else:
            left, right = st.columns([1, 2], gap="large")
            with left.expander("Add Custom Exercise"):
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

            with right.expander("Custom Exercise List", expanded=True):
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
                        edit_group = st.text_input(
                            "Group", group, key=f"cust_group_{name}"
                        )
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
                        edit_other = st.text_input(
                            "Other", other, key=f"cust_oth_{name}"
                        )
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
        favs = self.favorite_workouts_repo.fetch_all()
        with st.expander("Favorite Workouts", expanded=True):
            if favs:
                for fid in favs:
                    try:
                        _id, date, *_ = self.workouts.fetch_detail(fid)
                    except ValueError:
                        continue
                    cols = st.columns(2)
                    cols[0].write(date)
                    if cols[1].button("Remove", key=f"fav_wk_rm_{fid}"):
                        self.favorite_workouts_repo.remove(fid)
                        st.rerun()
            else:
                st.write("No favorites.")
            all_workouts = {str(w[0]): w[1] for w in self.workouts.fetch_all_workouts()}
            add_choice = st.selectbox(
                "Add Favorite",
                [""] + list(all_workouts.keys()),
                format_func=lambda x: "" if x == "" else all_workouts[x],
                key="fav_wk_add_choice",
            )
            if st.button("Add Favorite", key="fav_wk_add_btn") and add_choice:
                self.favorite_workouts_repo.add(int(add_choice))
                st.rerun()
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
            if st.button("Reset", key="hist_reset"):
                st.session_state.hist_start = (
                    datetime.date.today() - datetime.timedelta(days=30)
                )
                st.session_state.hist_end = datetime.date.today()
                st.session_state.hist_type = ""
                st.session_state.hist_tags = []
                st.rerun()
            ttype = st.selectbox(
                "Training Type",
                ["", "strength", "hypertrophy", "highintensity"],
                key="hist_type",
            )
            tag_names = [n for _, n in self.tags_repo.fetch_all()]
            sel_tags = st.multiselect("Tags", tag_names, key="hist_tags")
            start_str = start.isoformat()
            end_str = end.isoformat()
        workouts = self.workouts.fetch_all_workouts(start_str, end_str)
        if ttype:
            workouts = [w for w in workouts if w[4] == ttype]
        if sel_tags:
            workouts = [
                w
                for w in workouts
                if set(sel_tags).issubset(
                    {n for _, n in self.tags_repo.fetch_for_workout(w[0])}
                )
            ]
        for wid, date, _s, _e, training_type, *_ in workouts:
            with st.expander(f"{date} ({training_type})", expanded=False):
                summary = self.sets.workout_summary(wid)
                st.markdown(
                    f"**Volume:** {summary['volume']} | **Sets:** {summary['sets']} | **Avg RPE:** {summary['avg_rpe']}"
                )
                tags = [n for _, n in self.tags_repo.fetch_for_workout(wid)]
                if tags:
                    st.markdown("**Tags:** " + ", ".join(tags))
                if st.button("Details", key=f"hist_det_{wid}"):
                    self._workout_details_dialog(wid)

    def _workout_details_dialog(self, workout_id: int) -> None:
        exercises = self.exercises.fetch_for_workout(workout_id)

        def _content() -> None:
            for ex_id, name, eq, note in exercises:
                sets = self.sets.fetch_for_exercise(ex_id)
                header = name if not eq else f"{name} ({eq})"
                if note:
                    header += f" - {note}"
                with st.expander(header, expanded=True):
                    for sid, reps, weight, rpe, stime, etime in sets:
                        line = f"{reps} reps x {weight} kg (RPE {rpe})"
                        if stime:
                            line += f" start: {stime}"
                        if etime:
                            line += f" end: {etime}"
                        st.write(line)

        self._show_dialog("Workout Details", _content)

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
            if st.button("Reset", key="stats_reset"):
                st.session_state.stats_start = (
                    datetime.date.today() - datetime.timedelta(days=30)
                )
                st.session_state.stats_end = datetime.date.today()
                st.session_state.stats_ex = ""
                st.rerun()
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
                self._line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    [d["date"] for d in daily],
                )
            equip_stats = self.stats.equipment_usage(start_str, end_str)
            st.table(equip_stats)
            eff_stats = self.stats.session_efficiency(start_str, end_str)
            if eff_stats:
                with st.expander("Session Efficiency", expanded=False):
                    st.table(eff_stats)
                    self._line_chart(
                        {"Efficiency": [e["efficiency"] for e in eff_stats]},
                        [e["date"] for e in eff_stats],
                    )
        with dist_tab:
            rpe_dist = self.stats.rpe_distribution(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if rpe_dist:
                self._bar_chart(
                    {"Count": [d["count"] for d in rpe_dist]},
                    [str(d["rpe"]) for d in rpe_dist],
                )
            reps_dist = self.stats.reps_distribution(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if reps_dist:
                self._bar_chart(
                    {"Count": [d["count"] for d in reps_dist]},
                    [str(d["reps"]) for d in reps_dist],
                )
            intensity = self.stats.intensity_distribution(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if intensity:
                df = pd.DataFrame(intensity).set_index("zone")
                st.bar_chart(df["volume"], use_container_width=True)
        with prog_tab:
            if ex_choice:
                prog = self.stats.progression(ex_choice, start_str, end_str)
                if prog:
                    self._line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        [p["date"] for p in prog],
                    )
                vel_hist = self.stats.velocity_history(ex_choice, start_str, end_str)
                if vel_hist:
                    with st.expander("Velocity History", expanded=False):
                        self._line_chart(
                            {"Velocity": [v["velocity"] for v in vel_hist]},
                            [v["date"] for v in vel_hist],
                        )
                self._progress_forecast_section(ex_choice)
            self._volume_forecast_section(start_str, end_str)
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
                self._line_chart(
                    {"TSB": [d["tsb"] for d in tsb]},
                    [d["date"] for d in tsb],
                )
            overview = self.stats.stress_overview(start_str, end_str)
            if overview:
                metrics = [
                    ("Stress", overview["stress"]),
                    ("Fatigue", overview["fatigue"]),
                ]
                self._metric_grid(metrics)

    def _progress_forecast_section(self, exercise: str) -> None:
        st.subheader("Progress Forecast")
        weeks = st.slider("Weeks", 1, 12, 4, key="forecast_weeks")
        wpw = st.slider("Workouts per Week", 1, 7, 3, key="forecast_wpw")
        if st.button("Show Forecast"):
            forecast = self.stats.progress_forecast(exercise, weeks, wpw)
            if forecast:
                self._line_chart(
                    {"Est 1RM": [f["est_1rm"] for f in forecast]},
                    [str(f["week"]) for f in forecast],
                )

    def _volume_forecast_section(self, start: str, end: str) -> None:
        st.subheader("Volume Forecast")
        days = st.slider("Days", 1, 14, 7, key="vol_forecast_days")
        if st.button("Show Volume Forecast"):
            data = self.stats.volume_forecast(days, start, end)
            if data:
                self._line_chart(
                    {"Volume": [d["volume"] for d in data]},
                    [d["date"] for d in data],
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
                end = st.date_input("End", datetime.date.today(), key="insights_end")
            if st.button("Reset", key="insights_reset"):
                st.session_state.insights_start = (
                    datetime.date.today() - datetime.timedelta(days=90)
                )
                st.session_state.insights_end = datetime.date.today()
                st.session_state.insights_ex = ""
                st.rerun()
        if ex_choice:
            insights = self.stats.progress_insights(
                ex_choice, start.isoformat(), end.isoformat()
            )
            prog = self.stats.progression(ex_choice, start.isoformat(), end.isoformat())
            if insights:
                with st.expander("Trend Analysis", expanded=True):
                    st.write(f"Trend: {insights.get('trend', '')}")
                    metrics = []
                    if "slope" in insights:
                        metrics.append(("Slope", round(insights["slope"], 2)))
                    if "r_squared" in insights:
                        metrics.append(("R\xb2", round(insights["r_squared"], 2)))
                    if "strength_seasonality" in insights:
                        metrics.append(
                            (
                                "Seasonality Strength",
                                round(insights["strength_seasonality"], 2),
                            )
                        )
                    metrics.append(("Plateau Score", insights["plateau_score"]))
                    self._metric_grid(metrics)
            if prog:
                with st.expander("1RM Progression", expanded=True):
                    self._line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        [p["date"] for p in prog],
                    )
        else:
            st.info("Select an exercise to view insights.")

    def _weight_tab(self) -> None:
        st.header("Body Weight")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="bw_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="bw_end")
            if st.button("Reset", key="bw_reset"):
                st.session_state.bw_start = datetime.date.today() - datetime.timedelta(
                    days=30
                )
                st.session_state.bw_end = datetime.date.today()
                st.rerun()
            start_str = start.isoformat()
            end_str = end.isoformat()
        stats = self.stats.weight_stats(start_str, end_str)
        with st.expander("Statistics", expanded=True):
            metrics = [
                ("Average", stats["avg"]),
                ("Min", stats["min"]),
                ("Max", stats["max"]),
            ]
            self._metric_grid(metrics)
        history = self.stats.body_weight_history(start_str, end_str)
        if history:
            with st.expander("Weight History", expanded=True):
                self._line_chart(
                    {"Weight": [h["weight"] for h in history]},
                    [h["date"] for h in history],
                )
        bmi_hist = self.stats.bmi_history(start_str, end_str)
        if bmi_hist:
            with st.expander("BMI History", expanded=False):
                self._line_chart(
                    {"BMI": [b["bmi"] for b in bmi_hist]},
                    [b["date"] for b in bmi_hist],
                )
        wellness = self.stats.wellness_summary(start_str, end_str)
        with st.expander("Wellness Summary", expanded=False):
            metrics = [
                ("Calories", wellness["avg_calories"]),
                ("Sleep Hours", wellness["avg_sleep"]),
                ("Sleep Quality", wellness["avg_quality"]),
                ("Stress Level", wellness["avg_stress"]),
            ]
            self._metric_grid(metrics)
        well_hist = self.stats.wellness_history(start_str, end_str)
        if well_hist:
            with st.expander("Wellness History", expanded=False):
                self._line_chart(
                    {
                        "Calories": [w["calories"] for w in well_hist],
                        "Sleep Hours": [w["sleep_hours"] for w in well_hist],
                        "Sleep Quality": [w["sleep_quality"] for w in well_hist],
                        "Stress": [w["stress_level"] for w in well_hist],
                    },
                    [w["date"] for w in well_hist],
                )
        with st.expander("Forecast", expanded=False):
            days = st.slider("Days", 1, 14, 7, key="bw_fc_days")
            if st.button("Show Forecast", key="bw_fc_btn"):
                forecast = self.stats.weight_forecast(days)
                if forecast:
                    self._line_chart(
                        {"Weight": [f["weight"] for f in forecast]},
                        [str(f["day"]) for f in forecast],
                    )

    def _reports_tab(self) -> None:
        st.header("Reports")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="rep_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="rep_end")
            if st.button("Reset", key="rep_reset"):
                st.session_state.rep_start = datetime.date.today() - datetime.timedelta(
                    days=30
                )
                st.session_state.rep_end = datetime.date.today()
                st.rerun()
            start_str = start.isoformat()
            end_str = end.isoformat()
        with st.expander("Overall Summary", expanded=True):
            summary = self.stats.overview(start_str, end_str)
            metrics = [
                ("Workouts", summary["workouts"]),
                ("Volume", summary["volume"]),
                ("Avg RPE", summary["avg_rpe"]),
                ("Exercises", summary["exercises"]),
            ]
            self._metric_grid(metrics)
        with st.expander("Top Exercises", expanded=True):
            data = self.stats.exercise_summary(None, start_str, end_str)
            data.sort(key=lambda x: x["volume"], reverse=True)
            if data:
                st.table(data[:5])
        with st.expander("Exercise Frequency", expanded=True):
            freq = self.stats.exercise_frequency(None, start_str, end_str)
            if freq:
                st.table(freq)
        with st.expander("Equipment Usage", expanded=True):
            eq_stats = self.stats.equipment_usage(start_str, end_str)
            if eq_stats:
                st.table(eq_stats)
                self._bar_chart(
                    {"Volume": [e["volume"] for e in eq_stats]},
                    [e["equipment"] for e in eq_stats],
                )
        with st.expander("Daily Volume", expanded=True):
            daily = self.stats.daily_volume(start_str, end_str)
            if daily:
                self._line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    [d["date"] for d in daily],
                )
        with st.expander("Training Strain", expanded=True):
            strain = self.stats.training_strain(start_str, end_str)
            if strain:
                self._line_chart(
                    {"Strain": [s["strain"] for s in strain]},
                    [s["week"] for s in strain],
                )
        with st.expander("Weekly Volume Change", expanded=False):
            wvc = self.stats.weekly_volume_change(start_str, end_str)
            if wvc:
                st.table(wvc)
                self._line_chart(
                    {"Change": [v["change"] for v in wvc]},
                    [v["week"] for v in wvc],
                )
        with st.expander("Session Duration", expanded=False):
            duration = self.stats.session_duration(start_str, end_str)
            if duration:
                st.table(duration)
                self._line_chart(
                    {"Duration": [d["duration"] for d in duration]},
                    [d["date"] for d in duration],
                )
        with st.expander("Session Density", expanded=False):
            density = self.stats.session_density(start_str, end_str)
            if density:
                st.table(density)
                self._line_chart(
                    {"Density": [d["density"] for d in density]},
                    [d["date"] for d in density],
                )
        with st.expander("Set Pace", expanded=False):
            pace = self.stats.set_pace(start_str, end_str)
            if pace:
                st.table(pace)
                self._line_chart(
                    {"Pace": [p["pace"] for p in pace]},
                    [p["date"] for p in pace],
                )
        with st.expander("Average Rest Times", expanded=False):
            rests = self.stats.rest_times(start_str, end_str)
            if rests:
                st.table(rests)
                self._bar_chart(
                    {"Rest": [r["avg_rest"] for r in rests]},
                    [str(r["workout_id"]) for r in rests],
                )
        with st.expander("Exercise Diversity", expanded=False):
            div = self.stats.exercise_diversity(start_str, end_str)
            if div:
                st.table(div)
                self._line_chart(
                    {"Diversity": [d["diversity"] for d in div]},
                    [d["date"] for d in div],
                )
        with st.expander("Time Under Tension", expanded=False):
            tut = self.stats.time_under_tension(start_str, end_str)
            if tut:
                st.table(tut)
                self._line_chart(
                    {"TUT": [t["tut"] for t in tut]},
                    [t["date"] for t in tut],
                )
        with st.expander("Location Summary", expanded=False):
            loc_stats = self.stats.location_summary(start_str, end_str)
            if loc_stats:
                st.table(loc_stats)
        with st.expander("Workout Consistency", expanded=False):
            consistency = self.stats.workout_consistency(start_str, end_str)
            metrics = [
                ("Consistency", consistency["consistency"]),
                ("Avg Gap (days)", consistency["average_gap"]),
            ]
            self._metric_grid(metrics)
        with st.expander("Rating Analysis", expanded=False):
            rating_hist = self.stats.rating_history(start_str, end_str)
            if rating_hist:
                self._line_chart(
                    {"Rating": [r["rating"] for r in rating_hist]},
                    [r["date"] for r in rating_hist],
                )
            stats = self.stats.rating_stats(start_str, end_str)
            metrics = [
                ("Average", stats["avg"]),
                ("Min", stats["min"]),
                ("Max", stats["max"]),
            ]
            self._metric_grid(metrics)

    def _risk_tab(self) -> None:
        st.header("Risk & Readiness")
        exercises = [""] + self.exercise_names_repo.fetch_all()
        with st.expander("Filters", expanded=True):
            ex_choice = st.selectbox("Exercise for Momentum", exercises, key="risk_ex")
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=30),
                    key="risk_start",
                )
            with col2:
                end = st.date_input("End", datetime.date.today(), key="risk_end")
            if st.button("Reset", key="risk_reset"):
                st.session_state.risk_start = (
                    datetime.date.today() - datetime.timedelta(days=30)
                )
                st.session_state.risk_end = datetime.date.today()
                st.session_state.risk_ex = ""
                st.rerun()
            start_str = start.isoformat()
            end_str = end.isoformat()
        summary = self.stats.adaptation_index(start_str, end_str)
        overtrain = self.stats.overtraining_risk(start_str, end_str)
        injury = self.stats.injury_risk(start_str, end_str)
        ready = self.stats.readiness(start_str, end_str)
        with st.expander("Summary", expanded=True):
            metrics = [
                ("Adaptation", summary["adaptation"]),
                ("Overtraining Risk", overtrain["risk"]),
                ("Injury Risk", injury["injury_risk"]),
            ]
            self._metric_grid(metrics)
        if ready:
            with st.expander("Readiness Trend", expanded=False):
                self._line_chart(
                    {"Readiness": [r["readiness"] for r in ready]},
                    [r["date"] for r in ready],
                )
        if ex_choice:
            momentum = self.stats.performance_momentum(ex_choice, start_str, end_str)
            self._metric_grid([("Momentum", momentum["momentum"])])

    def _gamification_tab(self) -> None:
        st.header("Gamification Stats")
        with st.expander("Summary", expanded=True):
            self._metric_grid([("Total Points", self.gamification.total_points())])
        with st.expander("Points by Workout", expanded=True):
            data = self.gamification.points_by_workout()
            if data:
                self._bar_chart(
                    {"Points": [p[1] for p in data]},
                    [str(p[0]) for p in data],
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

        with st.expander("Warmup Calculator", expanded=False):
            tgt = st.number_input(
                "Target Weight (kg)", min_value=0.0, step=0.5, key="warmup_target"
            )
            count = st.number_input(
                "Warmup Sets", min_value=1, step=1, value=3, key="warmup_sets"
            )
            if st.button("Calculate Warmup", key="warmup_calc"):
                try:
                    weights = MathTools.warmup_weights(float(tgt), int(count))
                    st.table(
                        [{"set": i + 1, "weight": w} for i, w in enumerate(weights)]
                    )
                except ValueError as e:
                    st.warning(str(e))

    def _calendar_tab(self) -> None:
        st.header("Calendar")
        with st.expander("Date Range", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "Start",
                    datetime.date.today() - datetime.timedelta(days=7),
                    key="cal_start",
                )
            with col2:
                end = st.date_input(
                    "End",
                    datetime.date.today() + datetime.timedelta(days=7),
                    key="cal_end",
                )
            if st.button("Reset", key="cal_reset"):
                st.session_state.pop("cal_start", None)
                st.session_state.pop("cal_end", None)
                st.rerun()
            start_str = start.isoformat()
            end_str = end.isoformat()
        logged = self.workouts.fetch_all_workouts(start_str, end_str)
        planned = self.planned_workouts.fetch_all(start_str, end_str)
        rows = []
        for wid, date, _s, _e, t_type, _notes, _rating in logged:
            rows.append(
                {
                    "date": date,
                    "type": t_type,
                    "planned": False,
                    "id": wid,
                }
            )
        for pid, date, t_type in planned:
            rows.append(
                {
                    "date": date,
                    "type": t_type,
                    "planned": True,
                    "id": pid,
                }
            )
        rows.sort(key=lambda x: x["date"])
        if rows:
            st.table(rows)

    def _goals_tab(self) -> None:
        st.header("Goals")
        with st.expander("Add Goal"):
            ex_names = [""] + self.exercise_names_repo.fetch_all()
            ex_choice = st.selectbox("Exercise", ex_names, key="goal_ex")
            name = st.text_input("Name", key="goal_name")
            value = st.number_input(
                "Target Value", min_value=0.0, step=0.1, key="goal_value"
            )
            unit = st.text_input("Unit", key="goal_unit")
            start_d = st.date_input(
                "Start Date", datetime.date.today(), key="goal_start"
            )
            target_d = st.date_input(
                "Target Date", datetime.date.today(), key="goal_target"
            )
            if st.button("Create Goal", key="goal_add"):
                if name and unit and ex_choice:
                    self.goals_repo.add(
                        ex_choice,
                        name,
                        float(value),
                        unit,
                        start_d.isoformat(),
                        target_d.isoformat(),
                    )
                    st.success("Added")
                else:
                    st.warning("Exercise, name and unit required")
        with st.expander("Existing Goals", expanded=True):
            rows = self.goals_repo.fetch_all()
            for gid, exn, gname, gval, gunit, sdate, tdate, ach in rows:
                exp = st.expander(f"{gname} - {gval}{gunit}")
                with exp:
                    names = self.exercise_names_repo.fetch_all()
                    ex_e = st.selectbox(
                        "Exercise",
                        names,
                        index=names.index(exn),
                        key=f"goal_ex_{gid}",
                    )
                    name_e = st.text_input("Name", gname, key=f"goal_name_{gid}")
                    val_e = st.number_input(
                        "Target Value",
                        value=float(gval),
                        step=0.1,
                        key=f"goal_value_{gid}",
                    )
                    unit_e = st.text_input("Unit", gunit, key=f"goal_unit_{gid}")
                    sdate_e = st.date_input(
                        "Start Date",
                        datetime.date.fromisoformat(sdate),
                        key=f"goal_start_{gid}",
                    )
                    tdate_e = st.date_input(
                        "Target Date",
                        datetime.date.fromisoformat(tdate),
                        key=f"goal_target_{gid}",
                    )
                    ach_e = st.checkbox(
                        "Achieved", value=bool(ach), key=f"goal_ach_{gid}"
                    )
                    cols = st.columns(2)
                    if cols[0].button("Update", key=f"goal_upd_{gid}"):
                        self.goals_repo.update(
                            gid,
                            ex_e,
                            name_e,
                            float(val_e),
                            unit_e,
                            sdate_e.isoformat(),
                            tdate_e.isoformat(),
                            ach_e,
                        )
                        st.success("Updated")
                    if cols[1].button("Delete", key=f"goal_del_{gid}"):
                        self.goals_repo.delete(gid)
                        st.success("Deleted")

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

            def _content() -> None:
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

            self._show_dialog("Confirm Deletion", _content)

        (
            gen_tab,
            eq_tab,
            mus_tab,
            ex_tab,
            cust_tab,
            bw_tab,
            well_tab,
            tag_tab,
        ) = st.tabs(
            [
                "General",
                "Equipment",
                "Muscles",
                "Exercise Aliases",
                "Custom Exercises",
                "Body Weight Logs",
                "Wellness Logs",
                "Workout Tags",
            ]
        )

        with gen_tab:
            st.header("General Settings")
            with st.expander("User Settings", expanded=True):
                bw = st.number_input(
                    "Body Weight (kg)",
                    min_value=1.0,
                    value=self.settings_repo.get_float("body_weight", 80.0),
                    step=0.5,
                )
                height = st.number_input(
                    "Height (m)",
                    min_value=0.5,
                    value=self.settings_repo.get_float("height", 1.75),
                    step=0.01,
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
            with st.expander("Gamification", expanded=True):
                game_enabled = st.checkbox(
                    "Enable Gamification",
                    value=self.gamification.is_enabled(),
                )
                self._metric_grid([("Total Points", self.gamification.total_points())])
            with st.expander("Machine Learning", expanded=True):
                ml_global = st.checkbox(
                    "Enable ML Models",
                    value=self.settings_repo.get_bool("ml_all_enabled", True),
                )
                ml_train = st.checkbox(
                    "Enable ML Training",
                    value=self.settings_repo.get_bool("ml_training_enabled", True),
                )
                ml_pred = st.checkbox(
                    "Enable ML Prediction",
                    value=self.settings_repo.get_bool("ml_prediction_enabled", True),
                )
                rpe_train = st.checkbox(
                    "RPE Model Training",
                    value=self.settings_repo.get_bool("ml_rpe_training_enabled", True),
                )
                rpe_pred = st.checkbox(
                    "RPE Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_rpe_prediction_enabled", True
                    ),
                )
                vol_train = st.checkbox(
                    "Volume Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_volume_training_enabled", True
                    ),
                )
                vol_pred = st.checkbox(
                    "Volume Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_volume_prediction_enabled", True
                    ),
                )
                read_train = st.checkbox(
                    "Readiness Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_readiness_training_enabled", True
                    ),
                )
                read_pred = st.checkbox(
                    "Readiness Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_readiness_prediction_enabled", True
                    ),
                )
                prog_train = st.checkbox(
                    "Progress Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_progress_training_enabled", True
                    ),
                )
                prog_pred = st.checkbox(
                    "Progress Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_progress_prediction_enabled", True
                    ),
                )
                goal_train = st.checkbox(
                    "Goal Model Training",
                    value=self.settings_repo.get_bool("ml_goal_training_enabled", True),
                )
                goal_pred = st.checkbox(
                    "Goal Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_goal_prediction_enabled", True
                    ),
                )
                inj_train = st.checkbox(
                    "Injury Model Training",
                    value=self.settings_repo.get_bool(
                        "ml_injury_training_enabled", True
                    ),
                )
                inj_pred = st.checkbox(
                    "Injury Model Prediction",
                    value=self.settings_repo.get_bool(
                        "ml_injury_prediction_enabled", True
                    ),
                )
            if st.button("Save General Settings"):
                self.settings_repo.set_float("body_weight", bw)
                self.settings_repo.set_float("height", height)
                self.settings_repo.set_float("months_active", ma)
                self.settings_repo.set_text("theme", theme_opt)
                self.theme = theme_opt
                self._apply_theme()
                self.gamification.enable(game_enabled)
                self.settings_repo.set_bool("ml_all_enabled", ml_global)
                self.settings_repo.set_bool("ml_training_enabled", ml_train)
                self.settings_repo.set_bool("ml_prediction_enabled", ml_pred)
                self.settings_repo.set_bool("ml_rpe_training_enabled", rpe_train)
                self.settings_repo.set_bool("ml_rpe_prediction_enabled", rpe_pred)
                self.settings_repo.set_bool("ml_volume_training_enabled", vol_train)
                self.settings_repo.set_bool("ml_volume_prediction_enabled", vol_pred)
                self.settings_repo.set_bool("ml_readiness_training_enabled", read_train)
                self.settings_repo.set_bool(
                    "ml_readiness_prediction_enabled", read_pred
                )
                self.settings_repo.set_bool("ml_progress_training_enabled", prog_train)
                self.settings_repo.set_bool("ml_progress_prediction_enabled", prog_pred)
                self.settings_repo.set_bool("ml_goal_training_enabled", goal_train)
                self.settings_repo.set_bool("ml_goal_prediction_enabled", goal_pred)
                self.settings_repo.set_bool("ml_injury_training_enabled", inj_train)
                self.settings_repo.set_bool("ml_injury_prediction_enabled", inj_pred)
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

        with bw_tab:
            st.header("Body Weight Logs")
            with st.expander("Add Entry"):
                bw_date = st.date_input(
                    "Date",
                    datetime.date.today(),
                    key="bw_date",
                )
                bw_val = st.number_input(
                    "Weight (kg)",
                    min_value=1.0,
                    step=0.1,
                    key="bw_val",
                )
                if st.button("Log Weight", key="bw_add"):
                    try:
                        self.body_weights_repo.log(bw_date.isoformat(), bw_val)
                        st.success("Logged")
                    except ValueError as e:
                        st.warning(str(e))

            with st.expander("History", expanded=True):
                rows = self.body_weights_repo.fetch_history()
                for rid, d, w in rows:
                    exp = st.expander(f"{d} - {w} kg")
                    with exp:
                        date_edit = st.date_input(
                            "Date",
                            datetime.date.fromisoformat(d),
                            key=f"bw_edit_date_{rid}",
                        )
                        weight_edit = st.number_input(
                            "Weight (kg)",
                            value=w,
                            min_value=1.0,
                            step=0.1,
                            key=f"bw_edit_val_{rid}",
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"bw_upd_{rid}"):
                            try:
                                self.body_weights_repo.update(
                                    rid,
                                    date_edit.isoformat(),
                                    weight_edit,
                                )
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"bw_del_{rid}"):
                            try:
                                self.body_weights_repo.delete(rid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))

            with st.expander("BMI History", expanded=False):
                bmi_hist = self.stats.bmi_history()
                if bmi_hist:
                    df_bmi = pd.DataFrame(bmi_hist).set_index("date")
                    st.line_chart(df_bmi["bmi"])

        with well_tab:
            st.header("Wellness Logs")
            with st.expander("Add Entry"):
                w_date = st.date_input(
                    "Date",
                    datetime.date.today(),
                    key="well_date",
                )
                calories = st.number_input(
                    "Calories", min_value=0.0, step=50.0, key="well_calories"
                )
                sleep_h = st.number_input(
                    "Sleep Hours", min_value=0.0, step=0.5, key="well_sleep"
                )
                sleep_q = st.number_input(
                    "Sleep Quality",
                    min_value=0.0,
                    max_value=5.0,
                    step=1.0,
                    key="well_quality",
                )
                stress = st.number_input(
                    "Stress Level", min_value=0, max_value=10, step=1, key="well_stress"
                )
                if st.button("Log Wellness", key="well_add"):
                    try:
                        self.wellness_repo.log(
                            w_date.isoformat(),
                            calories,
                            sleep_h,
                            sleep_q,
                            int(stress),
                        )
                        st.success("Logged")
                    except ValueError as e:
                        st.warning(str(e))

            with st.expander("History", expanded=True):
                rows = self.wellness_repo.fetch_history()
                for rid, d, cal, sh, sq, st_lvl in rows:
                    exp = st.expander(f"{d}")
                    with exp:
                        date_e = st.date_input(
                            "Date",
                            datetime.date.fromisoformat(d),
                            key=f"well_edit_date_{rid}",
                        )
                        cal_e = st.number_input(
                            "Calories",
                            value=cal or 0.0,
                            step=50.0,
                            key=f"well_edit_cal_{rid}",
                        )
                        sh_e = st.number_input(
                            "Sleep Hours",
                            value=sh or 0.0,
                            step=0.5,
                            key=f"well_edit_sleep_{rid}",
                        )
                        sq_e = st.number_input(
                            "Sleep Quality",
                            value=sq or 0.0,
                            step=1.0,
                            key=f"well_edit_quality_{rid}",
                        )
                        st_e = st.number_input(
                            "Stress Level",
                            value=st_lvl or 0,
                            step=1,
                            key=f"well_edit_stress_{rid}",
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"well_upd_{rid}"):
                            try:
                                self.wellness_repo.update(
                                    rid,
                                    date_e.isoformat(),
                                    cal_e,
                                    sh_e,
                                    sq_e,
                                    int(st_e),
                                )
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"well_del_{rid}"):
                            try:
                                self.wellness_repo.delete(rid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))

        with tag_tab:
            st.header("Workout Tags")
            with st.expander("Add Tag"):
                tag_name = st.text_input("Name", key="new_tag")
                if st.button("Add Tag", key="add_tag"):
                    if tag_name:
                        try:
                            self.tags_repo.add(tag_name)
                            st.success("Added")
                        except Exception as e:
                            st.warning(str(e))
                    else:
                        st.warning("Name required")

            with st.expander("Existing Tags", expanded=True):
                tags = self.tags_repo.fetch_all()
                for tid, name in tags:
                    exp = st.expander(name)
                    with exp:
                        name_edit = st.text_input(
                            "Name", value=name, key=f"tag_name_{tid}"
                        )
                        cols = st.columns(2)
                        if cols[0].button("Update", key=f"tag_upd_{tid}"):
                            try:
                                self.tags_repo.update(tid, name_edit)
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if cols[1].button("Delete", key=f"tag_del_{tid}"):
                            try:
                                self.tags_repo.delete(tid)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))


if __name__ == "__main__":
    import os

    db_path = os.environ.get("DB_PATH", "workout.db")
    yaml_path = os.environ.get("YAML_PATH", "settings.yaml")
    GymApp(db_path=db_path, yaml_path=yaml_path).run()
