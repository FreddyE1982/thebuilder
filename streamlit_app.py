import datetime
import pandas as pd
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator, Callable
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from altair.utils.deprecation import AltairDeprecationWarning
import warnings
import json
import time
import os

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
    MuscleGroupRepository,
    ExerciseNameRepository,
    ExerciseVariantRepository,
    SettingsRepository,
    PyramidTestRepository,
    PyramidEntryRepository,
    GamificationRepository,
    MLModelRepository,
    MLLogRepository,
    MLModelStatusRepository,
    AutoPlannerLogRepository,
    ExercisePrescriptionLogRepository,
    BodyWeightRepository,
    WellnessRepository,
    HeartRateRepository,
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
    RLGoalModelService,
)
from tools import MathTools, GitTools

# Preinitialize session state for library widget keys to prevent missing state
for _k, _default in {"lib_eq_name": "", "lib_ex_name": ""}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _default


class LayoutManager:
    """Manage top-level page layout and navigation."""

    @property
    def is_mobile(self) -> bool:
        return st.session_state.get("is_mobile", False)

    def start_page(self) -> None:
        st.markdown("<div class='page-wrapper'>", unsafe_allow_html=True)

    def end_page(self) -> None:
        st.markdown("</div>", unsafe_allow_html=True)

    def open_header(self) -> None:
        st.markdown(
            "<header class='header-wrapper'><div class='header-inner'>",
            unsafe_allow_html=True,
        )

    def close_header(self) -> None:
        st.markdown("</div></header>", unsafe_allow_html=True)

    def open_content(self) -> None:
        st.markdown("<main class='content-wrapper'>", unsafe_allow_html=True)

    def close_content(self) -> None:
        st.markdown("</main>", unsafe_allow_html=True)

    def _render_nav(self, container_class: str, selected_tab: int) -> None:
        labels = ["workouts", "library", "progress", "settings"]
        icons = {
            "workouts": "🏋️",
            "library": "📚",
            "progress": "📈",
            "settings": "⚙️",
        }
        mode = "mobile" if self.is_mobile else "desktop"
        html = (
            f'<nav class="{container_class}" role="tablist" aria-label="Main Navigation">'
            + "".join(
                f'<button role="tab" title="{label.title()}" '
                f'aria-label="{label.title()} Tab" '
                f'aria-selected="{str(selected_tab == idx).lower()}" '
                f'{"aria-current=\"page\" " if selected_tab == idx else ""}'
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

    def bottom_nav(self, selected_tab: int) -> None:
        if not self.is_mobile:
            return
        self._render_nav("bottom-nav", selected_tab)
        self.scroll_top_button()

    def top_nav(self, selected_tab: int) -> None:
        if self.is_mobile:
            return
        self._render_nav("top-nav", selected_tab)

    def scroll_top_button(self) -> None:
        st.markdown(
            """
            <button class='scroll-top' aria-label='Back to top' onclick="window.scrollTo({top:0,behavior:'smooth'});">⬆</button>
            """,
            unsafe_allow_html=True,
        )

    def scroll_to(self, element_id: str) -> None:
        """Scroll smoothly to the element with the given id."""
        components.html(
            f"<script>document.getElementById('{element_id}')?.scrollIntoView({{behavior:'smooth'}});</script>",
            height=0,
        )


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
        self.color_theme = self.settings_repo.get_text("color_theme", "red")
        self.auto_dark_mode = self.settings_repo.get_bool("auto_dark_mode", False)
        self.compact_mode = self.settings_repo.get_bool("compact_mode", False)
        self.large_font = self.settings_repo.get_bool("large_font_mode", False)
        self.side_nav = self.settings_repo.get_bool("side_nav", False)
        self.show_onboarding = self.settings_repo.get_bool("show_onboarding", False)
        self.auto_open_last_workout = self.settings_repo.get_bool("auto_open_last_workout", False)
        self.weight_unit = self.settings_repo.get_text("weight_unit", "kg")
        self.time_format = self.settings_repo.get_text("time_format", "24h")
        self.quick_weights = [
            float(v)
            for v in self.settings_repo.get_text(
                "quick_weights", "20,40,60,80,100"
            ).split(",")
            if v
        ]
        self.add_set_key = self.settings_repo.get_text("hotkey_add_set", "a")
        self.tab_keys = self.settings_repo.get_text(
            "hotkey_tab_keys", "1,2,3,4"
        )
        self.sidebar_width = self.settings_repo.get_float("sidebar_width", 18.0)
        self.training_options = sorted(
            [
                "strength",
                "hypertrophy",
                "highintensity",
            ]
        )
        self._configure_page()
        self._inject_responsive_css()
        self._apply_theme()
        self.layout = LayoutManager()
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.planned_workouts = PlannedWorkoutRepository(db_path)
        self.planned_exercises = PlannedExerciseRepository(db_path)
        self.planned_sets = PlannedSetRepository(db_path)
        self.template_workouts = TemplateWorkoutRepository(db_path)
        self.template_exercises = TemplateExerciseRepository(db_path)
        self.template_sets = TemplateSetRepository(db_path)
        self.equipment = EquipmentRepository(db_path, self.settings_repo)
        self.exercise_catalog = ExerciseCatalogRepository(db_path, self.settings_repo)
        self.muscles_repo = MuscleRepository(db_path)
        self.muscle_groups_repo = MuscleGroupRepository(db_path, self.muscles_repo)
        self.exercise_names_repo = ExerciseNameRepository(db_path)
        self.exercise_variants_repo = ExerciseVariantRepository(db_path)
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
        self.ml_status = MLModelStatusRepository(db_path)
        self.autoplan_logs = AutoPlannerLogRepository(db_path)
        self.prescription_logs = ExercisePrescriptionLogRepository(db_path)
        self.body_weights_repo = BodyWeightRepository(db_path)
        self.wellness_repo = WellnessRepository(db_path)
        self.heart_rates = HeartRateRepository(db_path)
        self.gamification = GamificationService(
            self.game_repo,
            self.exercises,
            self.settings_repo,
            self.workouts,
        )
        self.ml_service = PerformanceModelService(
            self.ml_models,
            self.exercise_names_repo,
            self.ml_logs,
            self.ml_status,
        )
        self.volume_model = VolumeModelService(
            self.ml_models, status_repo=self.ml_status
        )
        self.readiness_model = ReadinessModelService(
            self.ml_models, status_repo=self.ml_status
        )
        self.progress_model = ProgressModelService(
            self.ml_models, status_repo=self.ml_status
        )
        self.goal_model = RLGoalModelService(self.ml_models, status_repo=self.ml_status)
        self.recommender = RecommendationService(
            self.workouts,
            self.exercises,
            self.sets,
            self.exercise_names_repo,
            self.settings_repo,
            self.gamification,
            self.ml_service,
            self.goal_model,
            self.body_weights_repo,
            self.goals_repo,
            self.wellness_repo,
            prescription_log_repo=self.prescription_logs,
        )
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
            recommender=self.recommender,
            log_repo=self.autoplan_logs,
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
            self.exercise_catalog,
            self.workouts,
            self.heart_rates,
        )
        self._state_init()

    def _refresh(self) -> None:
        """Reload the application state."""
        if st.button("Refresh"):
            st.rerun()

    def _command_palette(self) -> None:
        if st.session_state.get("open_palette"):
            with st.dialog("Command Palette"):
                if st.button("Workouts"):
                    st.session_state.open_palette = False
                    st.experimental_set_query_params(tab="workouts")
                    st.rerun()
                if st.button("Library"):
                    st.session_state.open_palette = False
                    st.experimental_set_query_params(tab="library")
                    st.rerun()
                if st.button("Progress"):
                    st.session_state.open_palette = False
                    st.experimental_set_query_params(tab="progress")
                    st.rerun()
                if st.button("Settings"):
                    st.session_state.open_palette = False
                    st.experimental_set_query_params(tab="settings")
                    st.rerun()

    def _rest_timer(self) -> None:
        start = st.session_state.get("rest_start")
        if not start:
            return
        rest_sec = int(self.settings_repo.get_float("rest_timer_seconds", 90))
        remaining = rest_sec - int(time.time() - start)
        if remaining <= 0:
            st.session_state.pop("rest_start", None)
            st.info("Rest over!")
            return
        st.markdown(f"<div id='rest-timer'>Rest: {remaining}s</div>", unsafe_allow_html=True)
        if os.environ.get("TEST_MODE") != "1":
            components.html(
                "<script>setTimeout(()=>window.location.reload(),1000);</script>",
                height=0,
            )

    def _format_weight(self, weight: float) -> str:
        """Return weight formatted according to user settings."""
        if self.weight_unit == "lb":
            return f"{weight * 2.20462:.1f} lb"
        return f"{weight:.1f} kg"

    def _format_time(self, ts: str | datetime.datetime) -> str:
        """Return time formatted per user preference."""
        if isinstance(ts, str):
            ts = datetime.datetime.fromisoformat(ts)
        return ts.strftime("%I:%M %p") if self.time_format == "12h" else ts.strftime("%H:%M")

    def _configure_page(self) -> None:
        if st.session_state.get("layout_set"):
            return
        params = st.query_params
        if (
            self.auto_dark_mode
            and not st.session_state.get("auto_theme_done")
            and os.environ.get("TEST_MODE") is None
        ):
            pref = params.get("pref_dark")
            if pref is None:
                components.html(
                    """
                    <script>
                    const pref = window.matchMedia('(prefers-color-scheme: dark)').matches ? '1' : '0';
                    const params = new URLSearchParams(window.location.search);
                    params.set('pref_dark', pref);
                    window.location.search = params.toString();
                    </script>
                    """,
                    height=0,
                )
                st.stop()
            else:
                params.pop("pref_dark")
                new_theme = "dark" if pref == "1" else "light"
                if new_theme != self.theme:
                    self.settings_repo.set_text("theme", new_theme)
                    self.theme = new_theme
                    self._apply_theme()
                st.experimental_set_query_params(**params)
                st.session_state.auto_theme_done = True
        mode = params.get("mode")
        if params.get("cmd") == "1":
            st.session_state.open_palette = True
            params.pop("cmd")
            st.experimental_set_query_params(**params)
        if mode is None:
            components.html(
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
        components.html(
            (
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
            let lastScrollY = 0;
            function handleHeaderCollapse() {
                const header = document.querySelector('.header-wrapper');
                if (!header) return;
                const cur = window.pageYOffset;
                if (cur > lastScrollY && cur > header.offsetHeight) {
                    header.classList.add('collapsed');
                } else {
                    header.classList.remove('collapsed');
                }
                lastScrollY = cur;
            }
            function handleResize() {
                setMode();
                setVh();
                setSafeArea();
                setHeaderHeight();
                toggleScrollTopButton();
            }
            function saveScroll() {
                sessionStorage.setItem('scrollY', window.scrollY);
            }
            function persistExpanders() {
                const exps = Array.from(document.querySelectorAll('details'));
                exps.forEach(exp => {
                    const label = exp.querySelector('summary')?.innerText.trim() || '';
                    const key = `expander-${label}`;
                    const saved = sessionStorage.getItem(key);
                    if (saved !== null) exp.open = saved === 'true';
                    exp.addEventListener('toggle', () => {
                        sessionStorage.setItem(key, exp.open);
                    });
                });
            }
            window.addEventListener('resize', handleResize);
            window.addEventListener('orientationchange', handleResize);
            if (window.visualViewport) {
                window.visualViewport.addEventListener('resize', handleResize);
            }
            window.addEventListener('scroll', () => {
                toggleScrollTopButton();
                handleHeaderCollapse();
                saveScroll();
            });
            window.addEventListener('DOMContentLoaded', () => {
                handleResize();
                const y = sessionStorage.getItem('scrollY');
                if (y) window.scrollTo(0, parseInt(y));
                persistExpanders();
            });
            document.addEventListener('streamlit:rendered', () => {
                persistExpanders();
                const y = sessionStorage.getItem('scrollY');
                if (y) window.scrollTo(0, parseInt(y));
            });
            document.addEventListener('click', saveScroll, true);
            handleResize();
            const tabKeys = JSON.parse('%TAB_KEYS%');
            const addSetKey = '%ADD_KEY%'.toLowerCase();
            function handleHotkeys(e) {
                if (e.altKey && tabKeys.includes(e.key)) {
                    const labels = ['workouts','library','progress','settings'];
                    const idx = tabKeys.indexOf(e.key);
                    const params = new URLSearchParams(window.location.search);
                    params.set('tab', labels[idx]);
                    window.location.search = params.toString();
                } else if (e.altKey && e.key.toLowerCase() === addSetKey) {
                    const btn = Array.from(document.querySelectorAll('button'))
                        .find(b => b.innerText.trim() === 'Add Set');
                    if (btn) btn.click();
                } else if (e.ctrlKey && e.key.toLowerCase() === 'k') {
                    const params = new URLSearchParams(window.location.search);
                    params.set('cmd', '1');
                    window.location.search = params.toString();
                }
            }
            window.addEventListener('keydown', handleHotkeys);
            let touchX = 0;
            function handleTouchStart(e) { touchX = e.touches[0].clientX; }
            function handleTouchEnd(e) {
                const dx = e.changedTouches[0].clientX - touchX;
                if (Math.abs(dx) > 50) {
                    const labels = ['workouts','library','progress','settings'];
                    const params = new URLSearchParams(window.location.search);
                    let idx = labels.indexOf(params.get('tab') || 'workouts');
                    if (dx < 0 && idx < labels.length - 1) idx++;
                    else if (dx > 0 && idx > 0) idx--;
                    params.set('tab', labels[idx]);
                    window.location.search = params.toString();
                }
            }
            window.addEventListener('touchstart', handleTouchStart);
            window.addEventListener('touchend', handleTouchEnd);
            document.addEventListener('click', e => {
                const t = e.target;
                if (t.tagName === 'BUTTON' && t.innerText.trim() === 'Add Set' && navigator.vibrate) {
                    navigator.vibrate(50);
                }
            });
            document.addEventListener('input', saveScroll, true);
            document.addEventListener('change', saveScroll, true);
            window.addEventListener('beforeunload', saveScroll);
            </script>
            """
            )
            .replace('%TAB_KEYS%', json.dumps(self.tab_keys.split(',')))
            .replace('%ADD_KEY%', self.add_set_key),
            height=0,
        )

    def _inject_responsive_css(self) -> None:
        css = """
            <style>
            :root {{
                --section-bg: #fafafa;
                --accent-color: #ff4b4b;
                --header-bg: #ffffff;
                --border-color: #cccccc;
                --safe-bottom: 0px;
                --base-font-size: 16px;
                --sidebar-width: WIDTHrem;
            }}
            html {
                font-size: var(--base-font-size);
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
                transition: transform 0.3s ease-in-out;
            }
            .header-wrapper.collapsed {
                transform: translateY(-100%);
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
                    background: var(--header-bg);
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
                    background: var(--header-bg);
                    border-top: 1px solid var(--border-color);
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
                background: var(--header-bg);
                border-bottom: 1px solid var(--border-color);
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
            nav.side-nav {
                display: flex;
                flex-direction: column;
                gap: 0.25rem;
            }
            nav.side-nav button {
                justify-content: flex-start;
            }
            @media screen and (min-width: 1200px) {
                nav.side-nav {
                    position: sticky;
                    top: 4rem;
                }
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
                border-bottom: 2px solid var(--accent-color);
                background: #f0f0f0;
            }
            nav.bottom-nav button:focus, nav.top-nav button:focus {
                outline: 2px solid var(--accent-color);
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
            .order-list { list-style: none; padding: 0; margin: 0; }
            .order-list li { padding: 0.25rem 0.5rem; border: 1px solid var(--border-color); margin-bottom: 0.25rem; background: var(--section-bg); cursor: grab; }
            .metric-card {
                background: var(--section-bg);
                border-radius: 0.5rem;
                padding: 0.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .badge {
                display: inline-block;
                padding: 0.1rem 0.4rem;
                border-radius: 0.25rem;
                color: #fff;
                font-size: 0.75rem;
            }
            .training-badge { padding: 0.1rem 0.4rem; border-radius: 0.25rem; color: #fff; font-size: 0.75rem; }
            .tt-strength { background: #4caf50; }
            .tt-hypertrophy { background: #9c27b0; }
            .tt-highintensity { background: #f39c12; }
            .badge.success { background: #4caf50; }
            .badge.error { background: #e74c3c; }
            .badge.warning { background: #f1c40f; }
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
            @media screen and (min-width: 768px) {
                div[data-testid="stSidebar"] {
                    width: var(--sidebar-width) !important;
                    flex-basis: var(--sidebar-width) !important;
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
                background: var(--accent-color);
                color: #ffffff;
                font-size: 1.25rem;
                display: none;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                z-index: 1000;
            }
            .fab-container {
                position: fixed;
                right: 0.75rem;
                bottom: calc(var(--safe-bottom) + 7rem);
                z-index: 1000;
            }
            .fab-container button {
                width: 3rem;
                height: 3rem;
                border: none;
                border-radius: 50%;
                background: var(--accent-color);
                color: #ffffff;
                font-size: 1.5rem;
            }
            .help-container {
                position: fixed;
                right: 0.75rem;
                bottom: calc(var(--safe-bottom) + 3rem);
                z-index: 1000;
            }
            .help-container button {
                width: 2.5rem;
                height: 2.5rem;
                border: none;
                border-radius: 50%;
                background: var(--accent-color);
                color: #ffffff;
                font-size: 1.25rem;
            }
            .conn-status {
                font-size: 0.8rem;
                margin-left: auto;
            }
            .set-row {
                padding: 0.5rem;
                border-radius: 0.25rem;
                margin-bottom: 0.5rem;
            }
            .set-registered {
                background: var(--section-bg);
            }
            .set-unregistered {
                background: #ffcccc;
            }
            .flash {
                animation: flash 0.5s ease-in-out;
            }
            @keyframes flash {
                from { background-color: rgba(255,255,0,0.5); }
                to { background-color: transparent; }
            }
            .set-status {
                font-size: 0.8rem;
                color: green;
                margin-top: 0.25rem;
            }
            @media screen and (min-width: 769px) {
                .scroll-top {
                    bottom: 1rem;
                }
                .fab-container {
                    bottom: 2rem;
                }
            }
            </style>
            """
        st.markdown(
            css.replace("WIDTH", str(self.sidebar_width)), unsafe_allow_html=True
        )
        if self.large_font:
            st.markdown(
                "<style>:root{--base-font-size:18px;}</style>",
                unsafe_allow_html=True,
            )
        if self.compact_mode and not st.session_state.get("is_mobile", False):
            st.markdown(
                """
                <style>
                div[data-testid='stTable'] th,
                div[data-testid='stTable'] td {
                    padding: 0.25rem 0.5rem;
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
                    background-color: #121212;
                    color: #eee;
                }
                :root {
                    --section-bg: #1f1f1f;
                    --accent-color: #ff6b6b;
                    --header-bg: #2a2a2a;
                    --border-color: #444444;
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
                    --section-bg: #fafafa;
                    --accent-color: #ff4b4b;
                    --header-bg: #ffffff;
                    --border-color: #cccccc;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
        if self.color_theme == "colorblind":
            st.markdown(
                """
                <style>
                :root {
                    --accent-color: #0072B2;
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
        if "deleted_set" not in st.session_state:
            st.session_state.deleted_set = None
        if "flash_set" not in st.session_state:
            st.session_state.flash_set = None
        if "open_palette" not in st.session_state:
            st.session_state.open_palette = False
        if "auto_theme_done" not in st.session_state:
            st.session_state.auto_theme_done = False
        # ensure library widgets always have state available for testing
        if "lib_eq_name" not in st.session_state:
            st.session_state.lib_eq_name = ""
        if "lib_ex_name" not in st.session_state:
            st.session_state.lib_ex_name = ""
        for _k, _default in {
            "lib_eq_type": [],
            "lib_eq_prefix": "",
            "lib_eq_mus": [],
            "lib_ex_groups": [],
            "lib_ex_mus": [],
            "lib_ex_eq": "",
            "lib_ex_prefix": "",
        }.items():
            if _k not in st.session_state:
                st.session_state[_k] = _default

    def _create_sidebar(self) -> None:
        if self.side_nav and not st.session_state.get("is_mobile", False):
            self._render_nav("side-nav")
            st.sidebar.divider()
        st.sidebar.header("Quick Actions")
        if st.sidebar.button("New Workout"):
            wid = self.workouts.create(
                datetime.date.today().isoformat(),
                "strength",
                None,
                None,
            )
            self._select_workout(wid)
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
        with st.sidebar.expander("Quick Search"):
            self._quick_search("sidebar")

    def _render_nav(self, container_class: str) -> None:
        """Render navigation bar using LayoutManager."""
        selected = st.session_state.get("main_tab", 0)
        self.layout._render_nav(container_class, selected)

    def _bottom_nav(self) -> None:
        """Render bottom navigation on mobile devices."""
        selected = st.session_state.get("main_tab", 0)
        self.layout.bottom_nav(selected)

    def _scroll_top_button(self) -> None:
        self.layout.scroll_top_button()

    def _quick_search(self, prefix: str) -> None:
        """Search workouts by notes or location and open them."""
        query = st.text_input("Search", key=f"{prefix}_search")
        suggestions = (
            self.workouts.search(query)[:5] if query and len(query) >= 2 else []
        )
        if st.button("Search", key=f"{prefix}_search_btn"):
            st.session_state[f"{prefix}_search_results"] = (
                self.workouts.search(query) if query else []
            )
        results = st.session_state.get(f"{prefix}_search_results", [])
        if suggestions:
            opt_map = {f"{wid} - {date}": wid for wid, date in suggestions}
            pick = st.selectbox(
                "Suggestions", list(opt_map.keys()), key=f"{prefix}_suggest"
            )
            if st.button("Open", key=f"{prefix}_suggest_open"):
                self._select_workout(opt_map[pick])
                self._switch_tab("workouts")
        if results:
            options = {f"{wid} - {date}": wid for wid, date in results}
            choice = st.selectbox(
                "Results", list(options.keys()), key=f"{prefix}_search_sel"
            )
            if st.button("Open", key=f"{prefix}_search_open"):
                self._select_workout(options[choice])
                self._switch_tab("workouts")

    def _quick_workout_button(self) -> None:
        """Display floating button to quickly add a workout."""
        st.markdown("<div class='fab-container'>", unsafe_allow_html=True)
        if st.button("➕", key="quick_workout_btn"):
            st.session_state.open_quick_workout = True
        st.markdown("</div>", unsafe_allow_html=True)
        if st.session_state.get("open_quick_workout"):
            self._new_workout_dialog()

    def _help_overlay_button(self) -> None:
        """Floating help button opening overlay with README links."""
        st.markdown("<div class='help-container'>", unsafe_allow_html=True)
        if st.button("?", key="help_overlay_btn"):
            st.session_state.open_help_overlay = True
        st.markdown("</div>", unsafe_allow_html=True)
        if st.session_state.get("open_help_overlay"):
            self._help_overlay_dialog()

    def _context_menu(self) -> None:
        menu = """
        <div id='ctx-menu' style='display:none;position:absolute;z-index:10000;background:#fff;border:1px solid #ccc;'>
            <button onclick="ctxAct('copy')">Copy to Template</button>
            <button onclick="ctxAct('delete')">Delete</button>
        </div>
        <script>
        function ctxAct(action){
            const params=new URLSearchParams(window.location.search);
            params.set('ctx_action', action);
            params.set('ctx_id', window.currentCtxId);
            window.location.search=params.toString();
        }
        document.addEventListener('contextmenu',e=>{
            const t=e.target.closest('[data-workout-id]');
            if(t){
                e.preventDefault();
                window.currentCtxId=t.dataset.workoutId;
                const m=document.getElementById('ctx-menu');
                m.style.left=e.pageX+'px';
                m.style.top=e.pageY+'px';
                m.style.display='block';
            }
        });
        document.addEventListener('click',()=>{document.getElementById('ctx-menu').style.display='none';});
        </script>
        """
        st.markdown(menu, unsafe_allow_html=True)

    def _connection_status(self) -> None:
        """Display connection status for API and database."""
        try:
            self.workouts.fetch_all_workouts()
            db_icon = "🟢"
        except Exception:
            db_icon = "🔴"
        st.markdown(
            f"<div class='conn-status'>DB {db_icon} API 🟢</div>",
            unsafe_allow_html=True,
        )

    def _top_nav(self) -> None:
        """Render top navigation on desktop."""
        selected = st.session_state.get("main_tab", 0)
        self.layout.top_nav(selected)

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

    def _line_chart(
        self,
        data: dict[str, list],
        x: list[str],
        *,
        x_label: str = "x",
        y_label: str = "value",
    ) -> None:
        """Render a consistent line chart with accessible labels."""
        df = pd.DataFrame({"x": x})
        for key, values in data.items():
            df[key] = values
        long_df = df.melt("x", var_name="series", value_name="value")
        chart = (
            alt.Chart(long_df)
            .mark_line()
            .encode(
                x=alt.X("x", title=x_label),
                y=alt.Y("value", title=y_label),
                color=alt.Color(
                    "series",
                    scale=alt.Scale(scheme="dark2"),
                    legend=None if len(data) == 1 else alt.Legend(title="Series"),
                ),
            )
        )
        st.altair_chart(chart, use_container_width=True)

    def _bar_chart(
        self,
        data: dict[str, list],
        x: list[str],
        *,
        x_label: str = "x",
        y_label: str = "value",
    ) -> None:
        """Render a consistent bar chart with accessible labels."""
        df = pd.DataFrame({"x": x})
        for key, values in data.items():
            df[key] = values
        long_df = df.melt("x", var_name="series", value_name="value")
        chart = (
            alt.Chart(long_df)
            .mark_bar()
            .encode(
                x=alt.X("x", title=x_label),
                y=alt.Y("value", title=y_label),
                color=alt.Color(
                    "series",
                    scale=alt.Scale(scheme="dark2"),
                    legend=None if len(data) == 1 else alt.Legend(title="Series"),
                ),
            )
        )
        st.altair_chart(chart, use_container_width=True)

    def _chart_carousel(self, charts: list[Callable[[], None]], key: str) -> None:
        """Display charts in a simple carousel."""
        if not charts:
            return
        idx = st.session_state.get(key, 0)
        cols = st.columns([1, 6, 1])
        with cols[0]:
            if st.button("◀", key=f"{key}_prev"):
                idx = (idx - 1) % len(charts)
                st.session_state[key] = idx
        with cols[1]:
            charts[idx]()
        with cols[2]:
            if st.button("▶", key=f"{key}_next"):
                idx = (idx + 1) % len(charts)
                st.session_state[key] = idx

    def _responsive_table(self, data: list[dict] | pd.DataFrame) -> None:
        """Render a table that collapses into expanders on mobile."""
        df = pd.DataFrame(data)
        if self.layout.is_mobile:
            for _, row in df.iterrows():
                label = str(row.iloc[0])
                with st.expander(label):
                    st.table(pd.DataFrame(row).T)
        else:
            st.table(df)

    def _show_dialog(self, title: str, content_fn: Callable[[], None]) -> None:
        """Display a modal dialog using the decorator API."""

        @st.dialog(title)
        def _dlg() -> None:
            content_fn()
            st.markdown(
                """
                <script>
                const dlg = document.querySelector('div[data-testid="stDialog"]');
                if (dlg) {
                  dlg.setAttribute('tabindex','0');
                  const focusable = dlg.querySelector('input,textarea,select,button');
                  if (focusable) { focusable.focus(); }
                  let startY = 0;
                  dlg.addEventListener('touchstart', e => { startY = e.touches[0].clientY; });
                  dlg.addEventListener('touchend', e => {
                    const dy = e.changedTouches[0].clientY - startY;
                    if (dy > 50) {
                      const close = dlg.querySelector('button[aria-label="Close"]');
                      if (close) close.click();
                    }
                  });
                }
                </script>
                """,
                unsafe_allow_html=True,
            )

        _dlg()

    def _add_help(self, text: str) -> None:
        class _Tooltip:
            pass

        _Tooltip.__doc__ = text
        st.help(_Tooltip)

    def _tab_tips(self, tips: list[str]) -> None:
        """Display a collapsible tips section."""
        with st.expander("Tips", expanded=False):
            for tip in tips:
                st.write(f"- {tip}")

    def _slugify(self, text: str) -> str:
        """Create a safe slug from a section title."""
        return text.lower().replace(" ", "_")

    @contextmanager
    def _section(self, title: str) -> Generator[None, None, None]:
        """Context manager for a styled section with an id for navigation."""
        ident = self._slugify(title)
        st.markdown(
            f"<div id='{ident}' class='section-wrapper'>", unsafe_allow_html=True
        )
        st.header(title)
        try:
            yield
        finally:
            st.markdown("</div>", unsafe_allow_html=True)

    def _start_page(self) -> None:
        """Open the page wrapper."""
        self.layout.start_page()

    def _open_header(self) -> None:
        """Open the header container."""
        self.layout.open_header()

    def _close_header(self) -> None:
        """Close the header container."""
        self.layout.close_header()

    def _end_page(self) -> None:
        """Close the page wrapper."""
        self.layout.end_page()

    def _open_content(self) -> None:
        """Begin main content container."""
        self.layout.open_content()

    def _close_content(self) -> None:
        """End main content container."""
        self.layout.close_content()

    def _jump_to_section(self, sections: list[str], key: str) -> None:
        """Provide a select box to quickly jump to a section."""
        choice = st.selectbox("Jump to Section", [""] + sections, key=key)
        if choice:
            st.session_state.scroll_to = self._slugify(choice)
            st.rerun()

    def _reset_equipment_filters(self) -> None:
        """Clear equipment library filter inputs."""
        st.session_state.lib_eq_type = []
        st.session_state.lib_eq_prefix = ""
        st.session_state.lib_eq_mus = []
        if os.environ.get("TEST_MODE") != "1":
            st.rerun()

    def _reset_exercise_filters(self) -> None:
        """Clear exercise library filter inputs."""
        st.session_state.lib_ex_groups = []
        st.session_state.lib_ex_mus = []
        st.session_state.lib_ex_eq = ""
        st.session_state.lib_ex_prefix = ""
        if os.environ.get("TEST_MODE") != "1":
            st.rerun()

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

    def _help_overlay_dialog(self) -> None:
        def _content() -> None:
            st.markdown("## Help Topics")
            readme = Path(__file__).with_name("README.md")
            if readme.exists():
                with open(readme, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("#"):
                            lvl = line.count("#")
                            title = line.strip("# ").strip()
                            anchor = title.lower().replace(" ", "-")
                            indent = "  " * (lvl - 1)
                            st.markdown(f"{indent}- [{title}](README.md#{anchor})")
            st.button("Close", key="help_overlay_close")

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

    def _analytics_tutorial_dialog(self) -> None:
        def _content() -> None:
            st.markdown("## Advanced Analytics Tutorial")
            steps = [
                "1. Choose an exercise and date range to analyze.",
                "2. Review trend analysis charts for progression insights.",
                "3. Explore velocity and power history for performance cues.",
                "4. Check stress balance to monitor fatigue versus recovery.",
                "5. Combine these metrics with gamification points for motivation.",
            ]
            for s in steps:
                st.markdown(s)
            if st.button("Close", key="analytics_tut_close"):
                st.session_state.show_analytics_tutorial = False

        self._show_dialog("Analytics Tutorial", _content)

    def _onboarding_wizard(self) -> None:
        """Display onboarding steps for first-time users."""

        steps = [
            "Welcome to The Builder! Log and plan your workouts easily.",
            "Add workouts in the Workouts tab and record each set with reps, weight and RPE.",
            "Analyze progress in the Progress tab and adjust settings to your preference.",
        ]
        step = st.session_state.get("onboarding_step", 0)

        def _content() -> None:
            st.markdown(steps[step])
            col1, col2 = st.columns(2)
            if step > 0:
                if col1.button("Back", key="onboard_back"):
                    st.session_state.onboarding_step -= 1
                    st.rerun()
            if step < len(steps) - 1:
                if col2.button("Next", key="onboard_next"):
                    st.session_state.onboarding_step += 1
                    st.rerun()
            else:
                if col2.button("Finish", key="onboard_finish"):
                    self.settings_repo.set_bool("onboarding_complete", True)
                    st.session_state.pop("onboarding_step", None)
                    st.rerun()

        self._show_dialog("Welcome", _content)

    def _close_quick_workout(self) -> None:
        st.session_state.open_quick_workout = False

    def _select_workout(self, workout_id: int) -> None:
        try:
            self.workouts.fetch_detail(workout_id)
        except Exception:
            return
        st.session_state.selected_workout = workout_id
        self.settings_repo.set_int("last_workout_id", workout_id)

    def _new_workout_dialog(self) -> None:
        def _content() -> None:
            with st.form("quick_workout_form"):
                new_type = st.selectbox(
                    "Training Type",
                    self.training_options,
                    index=self.training_options.index("strength"),
                    key="quick_workout_type",
                )
                self._add_help("Training focus for this workout")
                new_loc = st.text_input("Location", key="quick_workout_loc")
                self._add_help("Workout location")
                submitted = st.form_submit_button("Create")
                if submitted:
                    wid = self.workouts.create(
                        datetime.date.today().isoformat(),
                        new_type,
                        None,
                        new_loc or None,
                        None,
                    )
                    self._select_workout(wid)
                    st.session_state.open_quick_workout = False
                    st.rerun()
            st.button("Close", on_click=self._close_quick_workout)

        self._show_dialog("Quick New Workout", _content)

    def _dashboard_tab(self, prefix: str = "dash") -> None:
        if os.environ.get("TEST_MODE") == "1":
            return
        with self._section("Dashboard"):
            with st.expander("Filters", expanded=True):
                if st.session_state.is_mobile:
                    start = st.date_input(
                        "Start",
                        datetime.date.today() - datetime.timedelta(days=30),
                        key=f"{prefix}_start_m",
                    )
                    end = st.date_input("End", datetime.date.today(), key=f"{prefix}_end_m")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        start = st.date_input(
                            "Start",
                            datetime.date.today() - datetime.timedelta(days=30),
                            key=f"{prefix}_start_d",
                        )
                    with col2:
                        end = st.date_input(
                            "End", datetime.date.today(), key=f"{prefix}_end_d"
                        )
                if st.button("Reset", key=f"{prefix}_reset"):
                    st.session_state[f"{prefix}_start_d"] = (
                        datetime.date.today() - datetime.timedelta(days=30)
                    )
                    st.session_state[f"{prefix}_end_d"] = datetime.date.today()
                    st.session_state[f"{prefix}_start_m"] = (
                        datetime.date.today() - datetime.timedelta(days=30)
                    )
                    st.session_state[f"{prefix}_end_m"] = datetime.date.today()
                    st.rerun()
        stats = self.stats.overview(start.isoformat(), end.isoformat())
        w_stats = self.stats.weight_stats(start.isoformat(), end.isoformat())
        r_stats = self.stats.readiness_stats(start.isoformat(), end.isoformat())
        with st.expander("Overview Metrics", expanded=True):
            metrics = [
                ("Workouts", stats["workouts"]),
                ("Volume", stats["volume"]),
                ("Avg RPE", stats["avg_rpe"]),
                ("Exercises", stats["exercises"]),
                ("Avg Density", stats.get("avg_density", 0)),
                ("BMI", self.stats.bmi()),
                ("Avg Weight", w_stats["avg"]),
                ("Avg Readiness", r_stats["avg"]),
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
                    "Exercise Progression", exercises, key=f"{prefix}_ex"
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
                        "Exercise Progression", exercises, key=f"{prefix}_ex"
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
                    self._responsive_table(records[:5])
            if not st.session_state.is_mobile:
                top_ex = self.stats.exercise_summary(
                    None, start.isoformat(), end.isoformat()
                )
                top_ex.sort(key=lambda x: x["volume"], reverse=True)
                if top_ex:
                    with st.expander("Top Exercises", expanded=False):
                        self._responsive_table(top_ex[:5])

    def _summary_tab(self) -> None:
        with self._section("Summary"):
            self._dashboard_tab(prefix="sumdash")
            with st.expander("Gamification", expanded=True):
                self._metric_grid([("Total Points", self.gamification.total_points())])
            with st.expander("Weekly Streak", expanded=True):
                streak = self.stats.weekly_streak()
                self._metric_grid(
                    [
                        ("Current Weekly Streak", streak["current"]),
                        ("Best Weekly Streak", streak["best"]),
                    ]
                )

    def run(self) -> None:
        params = dict(st.query_params)
        self._handle_context_action(params)
        params = dict(st.query_params)
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
        if self.auto_open_last_workout and st.session_state.get("selected_workout") is None:
            wid = self.settings_repo.get_int("last_workout_id", 0)
            if wid:
                try:
                    self.workouts.fetch_detail(wid)
                    st.session_state.selected_workout = wid
                except Exception:
                    pass
        if (
            os.environ.get("TEST_MODE") is None
            and self.show_onboarding
            and not self.settings_repo.get_bool("onboarding_complete", False)
        ):
            self._onboarding_wizard()
        self._open_header()
        st.markdown("<div class='title-section'>", unsafe_allow_html=True)
        cols = st.columns([3, 1, 1, 3])
        with cols[0]:
            st.title("Workout Logger")
        with cols[1]:
            if st.button("Toggle Theme", key="toggle_theme_header"):
                new_theme = "dark" if self.theme == "light" else "light"
                self.settings_repo.set_text("theme", new_theme)
                self.theme = new_theme
                self._apply_theme()
                st.rerun()
        with cols[2]:
            if st.button("Help", key="help_button_header"):
                self._help_dialog()
        with cols[3]:
            with st.expander("Quick Search", expanded=False):
                self._quick_search("header")
        self._connection_status()
        st.markdown("</div>", unsafe_allow_html=True)
        self._top_nav()
        self._close_header()
        self._create_sidebar()
        self._open_content()
        self._refresh()
        self._command_palette()
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
                    summary_sub,
                    calendar_sub,
                    history_sub,
                    dash_sub,
                    stats_sub,
                    insights_sub,
                    weight_sub,
                    well_sub,
                    rep_sub,
                    risk_sub,
                    game_sub,
                    tests_sub,
                    goals_sub,
                ) = st.tabs(
                    [
                        "Summary",
                        "Calendar",
                        "History",
                        "Dashboard",
                        "Exercise Stats",
                        "Insights",
                        "Body Weight",
                        "Wellness Logs",
                        "Reports",
                        "Risk",
                        "Gamification",
                        "Tests",
                        "Goals",
                    ]
                )
                with summary_sub:
                    self._summary_tab()
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
                with well_sub:
                    self._wellness_tab()
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
        self._quick_workout_button()
        self._help_overlay_button()
        self._context_menu()
        self._bottom_nav()
        self._end_page()
        target = st.session_state.pop("scroll_to", None)
        if target:
            self.layout.scroll_to(target)

    def _log_tab(self) -> None:
        self._tab_tips(
            [
                "Record start and end times for accurate pace analytics.",
                "Use quick-add buttons for your favorite exercises.",
            ]
        )
        self._rest_timer()
        self._mini_calendar_widget()
        plans = sorted(self.planned_workouts.fetch_all(), key=lambda p: p[1])
        options = {str(p[0]): p for p in plans}
        today = datetime.date.today().isoformat()
        if plans:
            upcoming = [p for p in plans if p[1] >= today]
            if upcoming:
                with st.expander("Upcoming Planned Workouts", expanded=False):
                    for pid, pdate, ptype in upcoming[:3]:
                        st.markdown(f"- {pdate} ({ptype})")
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
                    self._select_workout(new_id)

        daily = self.stats.daily_volume(today, today)
        if daily:
            metrics = [
                ("Today's Volume", daily[0]["volume"]),
                ("Sets", daily[0]["sets"]),
            ]
            self._metric_grid(metrics)
        sections = ["Workouts"]
        if st.session_state.selected_workout:
            sections.append("Exercises")
        self._jump_to_section(sections, "log_jump")
        self._workout_section()
        if st.session_state.selected_workout:
            self._exercise_section()

    def _plan_tab(self) -> None:
        self._tab_tips(
            [
                "Generate AI plans or manage existing ones here.",
                "Drag and drop planned sets to reorder before using them.",
            ]
        )
        today = datetime.date.today().isoformat()
        overdue = [
            p for p in self.planned_workouts.fetch_all(end_date=today)
            if p[1] < today
        ]
        if overdue:
            st.warning(f"{len(overdue)} planned workouts are overdue!")
        with st.expander("AI Planner", expanded=False):
            ai_date = st.date_input(
                "Plan Date", datetime.date.today(), key="ai_plan_date"
            )
            names = self.exercise_catalog.fetch_names(None, None, None, None)
            ex_sel = st.multiselect("Exercises", names, key="ai_plan_exercises")
            ai_type = st.selectbox(
                "Training Type",
                self.training_options,
                index=self.training_options.index("strength"),
                key="ai_plan_type",
            )
            if st.button("Generate AI Plan", key="ai_plan_btn"):
                if ex_sel:
                    pairs = [(n, None) for n in ex_sel]
                    try:
                        pid = self.planner.create_ai_plan(
                            ai_date.isoformat(), pairs, ai_type
                        )
                        st.session_state.selected_planned_workout = pid
                        st.success("Plan created")
                    except ValueError as e:
                        st.warning(str(e))
                else:
                    st.warning("Select exercises")
        if st.query_params.get("tab") == "workouts":
            with st.expander("Templates", expanded=False):
                self._template_section()
                if st.session_state.get("selected_template") is not None:
                    self._template_exercise_section()
        with st.expander("Planned Workouts", expanded=True):
            self._planned_workout_section()
            if st.session_state.selected_planned_workout:
                self._planned_exercise_section()
        with st.expander("Recommendation History", expanded=False):
            last_s = self.autoplan_logs.last_success()
            st.write(f"Last success: {last_s or 'never'}")
            errs = self.autoplan_logs.last_errors(10)
            if errs:
                for ts, msg in errs:
                    st.write(f"{ts}: {msg}")

    def _workout_section(self) -> None:
        with self._section("Workouts"):
            with st.expander("Workout Management", expanded=True):
                create_tab, manage_tab = st.tabs(["Create New", "Existing"])
                with create_tab:
                    self._create_workout_form(self.training_options)
                with manage_tab:
                    self._existing_workout_form(self.training_options)

    def _create_workout_form(self, training_options: list[str]) -> None:
        with st.expander("Create New Workout"):
            with st.form("new_workout_form"):
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                new_type = st.selectbox(
                    "Training Type",
                    training_options,
                    index=training_options.index("strength"),
                    key="new_workout_type",
                )
                self._add_help("Select the primary training focus")
                new_location = st.text_input("Location", key="new_workout_location")
                self._add_help("Where the workout takes place")
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
                    self._select_workout(new_id)

    def _existing_workout_form(self, training_options: list[str]) -> None:
        with st.expander("Existing Workouts", expanded=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                search = st.text_input("Search", key="workout_search")
            with c2:
                if st.button("Reset Search", key="workout_search_reset"):
                    st.session_state.workout_search = ""
                    st.rerun()
            workouts = sorted(self.workouts.fetch_all_workouts(), key=lambda w: w[1])
            if search:
                query = search.lower()
                workouts = [w for w in workouts if query in (w[5] or "").lower()]
            options = {str(w[0]): w for w in workouts}
            if options:
                selected = st.selectbox(
                    "Select Workout",
                    list(options.keys()),
                    format_func=lambda x: options[x][1],
                )
                self._select_workout(int(selected))
                st.markdown(
                    f"<div data-workout-id='{selected}' class='workout-detail'>",
                    unsafe_allow_html=True,
                )
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
                        summary = self.sets.workout_summary(int(selected))
                        st.success(
                            f"Logged {summary['sets']} sets, volume {self._format_weight(summary['volume'])}, avg RPE {summary['avg_rpe']}"
                        )
                    type_choice = st.selectbox(
                        "Type",
                        training_options,
                        index=training_options.index(current_type),
                        key=f"type_select_{selected}",
                        on_change=self._update_workout_type,
                        args=(int(selected),),
                    )
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
                        summary = self.sets.workout_summary(int(selected))
                        st.success(
                            f"Logged {summary['sets']} sets, volume {self._format_weight(summary['volume'])}, avg RPE {summary['avg_rpe']}"
                        )
                    type_choice = cols[2].selectbox(
                        "Type",
                        training_options,
                        index=training_options.index(current_type),
                        key=f"type_select_{selected}",
                        on_change=self._update_workout_type,
                        args=(int(selected),),
                    )
                if start_time:
                    st.write(f"Start: {self._format_time(start_time)}")
                if end_time:
                    st.write(f"End: {self._format_time(end_time)}")
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                notes_edit = st.text_area(
                    "Notes",
                    value=notes_val,
                    key=f"workout_notes_{selected}",
                    on_change=self._update_workout_notes,
                    args=(int(selected),),
                )
                loc_edit = st.text_input(
                    "Location",
                    value=loc_val,
                    key=f"workout_location_{selected}",
                    on_change=self._update_workout_location,
                    args=(int(selected),),
                )
                rating_edit = st.slider(
                    "Rating",
                    0,
                    5,
                    value=rating_val if rating_val is not None else 0,
                    key=f"rating_{selected}",
                    on_change=self._update_workout_rating,
                    args=(int(selected),),
                )
                st.markdown("</div>", unsafe_allow_html=True)
                tags_all = self.tags_repo.fetch_all()
                current_tags = [
                    n for _, n in self.tags_repo.fetch_for_workout(int(selected))
                ]
                tag_sel = st.multiselect(
                    "Tags",
                    [n for _, n in tags_all],
                    current_tags,
                    key=f"tags_sel_{selected}",
                    on_change=self._update_workout_tags,
                    args=(int(selected),),
                )
                csv_data = self.sets.export_workout_csv(int(selected))
                st.download_button(
                    label="Export CSV",
                    data=csv_data,
                    file_name=f"workout_{selected}.csv",
                    mime="text/csv",
                    key=f"export_{selected}",
                )
                json_data = self.sets.export_workout_json(int(selected))
                st.download_button(
                    label="Export JSON",
                    data=json_data,
                    file_name=f"workout_{selected}.json",
                    mime="application/json",
                    key=f"export_json_{selected}",
                )
                if start_time and end_time:
                    link = f"?mode={'mobile' if self.layout.is_mobile else 'desktop'}&tab=progress&start={start_time}&end={end_time}"
                    st.link_button("View Analytics", link)
                if st.button("Copy to Template", key=f"copy_tpl_{selected}"):
                    tid = self.planner.copy_workout_to_template(int(selected))
                    st.success(f"Template {tid} created")
                if st.button("Delete Workout", key=f"del_workout_{selected}"):
                    self._confirm_delete_workout(int(selected))
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No workouts found.")

    def _planned_workout_section(self) -> None:
        with self._section("Planned Workouts"):
            with st.expander("Plan Management", expanded=True):
                create_tab, manage_tab = st.tabs(["Create New", "Existing"])
                with create_tab:
                    self._create_plan_form()
                with manage_tab:
                    self._existing_plan_form()

    def _create_plan_form(self) -> None:
        with st.expander("Create New Plan"):
            with st.form("new_plan_form"):
                st.markdown("<div class='form-grid'>", unsafe_allow_html=True)
                plan_date = st.date_input(
                    "Plan Date", datetime.date.today(), key="plan_date"
                )
                self._add_help("Date the workout is planned for")
                plan_type = st.selectbox(
                    "Training Type",
                    self.training_options,
                    index=self.training_options.index("strength"),
                    key="plan_type",
                )
                self._add_help("Planned workout focus")
                st.markdown("</div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("New Planned Workout")
                if submitted:
                    pid = self.planned_workouts.create(plan_date.isoformat(), plan_type)
                    st.session_state.selected_planned_workout = pid

    def _existing_plan_form(self) -> None:
        with st.expander("Existing Plans", expanded=True):
            plans = sorted(self.planned_workouts.fetch_all(), key=lambda x: x[1])
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
                            on_change=self._update_planned_workout,
                            args=(pid,),
                        )
                        type_choice = st.selectbox(
                            "Type",
                            self.training_options,
                            index=self.training_options.index(ptype),
                            key=f"plan_type_{pid}",
                            on_change=self._update_planned_workout,
                            args=(pid,),
                        )
                        dup_date = st.date_input(
                            "Duplicate To",
                            datetime.date.fromisoformat(pdate),
                            key=f"plan_dup_{pid}",
                        )
                        st.markdown("</div>", unsafe_allow_html=True)
                        if st.session_state.is_mobile:
                            if st.button("Duplicate", key=f"dup_plan_{pid}"):
                                self.planner.duplicate_plan(pid, dup_date.isoformat())
                                st.success("Duplicated")
                            if st.button("Delete", key=f"del_plan_{pid}"):
                                self.planned_workouts.delete(pid)
                                st.success("Deleted")
                        else:
                            cols = st.columns(3)
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
                if st.button("Add Exercise", key="open_add_ex_btn"):
                    st.session_state.open_add_ex_flag = True
                    st.session_state.scroll_to = "add_ex_form"
                favs = self.favorites_repo.fetch_all()
                if favs:
                    st.markdown("### Quick Add Favorites")
                    cols = st.columns(len(favs))
                    for idx, fav in enumerate(favs):
                        if cols[idx].button(fav, key=f"quick_add_{fav}"):
                            eq_name = None
                            detail = self.exercise_catalog.fetch_detail(fav)
                            if detail:
                                eq_names = detail[2]
                                if eq_names:
                                    eq_name = eq_names.split("|")[0]
                            ex_id = self.exercises.add(workout_id, fav, eq_name, None)
                            self.sets.add(ex_id, 1, 0.0, 0)
                            self.gamification.record_set(ex_id, 1, 0.0, 0)
                            st.session_state[f"open_ex_{ex_id}"] = True
                            st.session_state[f"open_add_set_{ex_id}"] = True
                            st.session_state.scroll_to = f"ex_{ex_id}_sets"
                            st.rerun()
                with st.expander(
                    "Add New Exercise",
                    expanded=st.session_state.get("open_add_ex_flag", False),
                ):
                    st.markdown("<div id='add_ex_form'></div>", unsafe_allow_html=True)
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
                    if st.button("Add Exercise", key="add_ex_btn"):
                        if ex_name and eq:
                            ex_id = self.exercises.add(
                                workout_id, ex_name, eq, note_val or None
                            )
                            self.sets.add(ex_id, 1, 0.0, 0)
                            self.gamification.record_set(ex_id, 1, 0.0, 0)
                            st.session_state.open_add_ex_flag = False
                            st.session_state[f"open_ex_{ex_id}"] = True
                            st.session_state[f"open_add_set_{ex_id}"] = True
                            st.session_state.scroll_to = f"ex_{ex_id}_sets"
                            st.rerun()
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
                self._heart_rate_section(workout_id)

    def _heart_rate_section(self, workout_id: int) -> None:
        """Display heart rate logs and summary for a workout."""
        with st.expander("Heart Rate", expanded=False):
            logs = self.heart_rates.fetch_for_workout(workout_id)
            if logs:
                df = pd.DataFrame(logs, columns=["id", "timestamp", "heart_rate"])
                self._responsive_table(df[["timestamp", "heart_rate"]])
                values = [int(r[2]) for r in logs]
                metrics = [
                    ("Avg", round(sum(values) / len(values), 2)),
                    ("Min", float(min(values))),
                    ("Max", float(max(values))),
                ]
                self._metric_grid(metrics)
            with st.form(f"hr_form_{workout_id}"):
                ts = st.text_input(
                    "Timestamp",
                    datetime.datetime.now().isoformat(timespec="seconds"),
                    key=f"hr_ts_{workout_id}",
                )
                rate = st.number_input(
                    "Heart Rate (bpm)",
                    min_value=30,
                    max_value=220,
                    step=1,
                    key=f"hr_val_{workout_id}",
                )
                if st.form_submit_button("Log Heart Rate"):
                    try:
                        self.heart_rates.log(
                            workout_id,
                            ts,
                            int(rate),
                        )
                        st.success("Logged")
                    except ValueError as e:
                        st.warning(str(e))

    def _exercise_card(
        self, exercise_id: int, name: str, equipment: Optional[str], note: Optional[str]
    ) -> None:
        sets = self.sets.fetch_for_exercise(exercise_id)
        st.markdown(f"<div id='ex_{exercise_id}'></div>", unsafe_allow_html=True)
        header = name if not equipment else f"{name} ({equipment})"
        if note:
            header += f" - {note}"
        expander = st.expander(
            header,
            expanded=st.session_state.pop(f"open_ex_{exercise_id}", False),
        )
        with expander:
            if st.button("Remove Exercise", key=f"remove_ex_{exercise_id}"):
                self._confirm_delete_exercise(exercise_id)
                return
            if st.button("Add Set", key=f"add_set_{exercise_id}"):
                reps_val = st.session_state.get(f"new_reps_{exercise_id}", 1)
                weight_val = st.session_state.get(f"new_weight_{exercise_id}", 0.0)
                rpe_val = st.session_state.get(f"new_rpe_{exercise_id}", 0)
                note_val = st.session_state.get(f"new_note_{exercise_id}", "")
                dur_val = st.session_state.get(f"new_duration_{exercise_id}", 0.0)
                self._submit_set(
                    exercise_id, reps_val, weight_val, rpe_val, note_val, dur_val
                )
            if equipment:
                muscles = self.equipment.fetch_muscles(equipment)
                st.markdown("**Muscles:**")
                for m in muscles:
                    st.markdown(f"- {m}")
            note_val = st.text_input(
                "Note",
                value=note or "",
                key=f"exercise_note_{exercise_id}",
            )
            if st.button("Update Note", key=f"upd_note_{exercise_id}"):
                self.exercises.update_note(exercise_id, note_val or None)
            if st.button("Clear Note", key=f"clear_note_{exercise_id}"):
                self.exercises.update_note(exercise_id, None)
                st.session_state[f"exercise_note_{exercise_id}"] = ""
            variants = self.exercise_variants_repo.fetch_variants(name)
            if variants:
                st.markdown("**Variants:**")
                for v in variants:
                    if st.button(v, key=f"switch_{exercise_id}_{v}"):
                        self.exercises.update_name(exercise_id, v)
                        st.rerun()
            with st.expander("Sets", expanded=True):
                order = [s[0] for s in sets]
                for idx, (
                    set_id,
                    reps,
                    weight,
                    rpe,
                    start_time,
                    end_time,
                    warm,
                    _position,
                ) in enumerate(sets, start=1):
                    detail = self.sets.fetch_detail(set_id)
                    registered = start_time is not None and end_time is not None
                    row_class = "set-registered" if registered else "set-unregistered"
                    if st.session_state.get("flash_set") == set_id:
                        row_class += " flash"
                        st.session_state.flash_set = None
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {idx}"):
                            st.markdown(
                                f"<div class='set-row {row_class}'>",
                                unsafe_allow_html=True,
                            )
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"reps_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
                            )
                            weight_val = st.number_input(
                                f"Weight ({self.weight_unit})",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"weight_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"rpe_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
                            )
                            warm_val = st.checkbox(
                                "Warmup",
                                value=bool(detail.get("warmup")),
                                key=f"warm_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
                            )
                            note_val = st.text_input(
                                "Note",
                                value=detail.get("note") or "",
                                key=f"note_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
                            )
                            dur_default = 0.0
                            if start_time and end_time:
                                t0 = datetime.datetime.fromisoformat(start_time)
                                t1 = datetime.datetime.fromisoformat(end_time)
                                dur_default = (t1 - t0).total_seconds()
                            duration_val = st.number_input(
                                "Duration (sec)",
                                min_value=0.0,
                                step=1.0,
                                value=dur_default,
                                key=f"duration_{set_id}",
                                on_change=self._update_set,
                                args=(set_id,),
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
                                st.rerun()
                            if finish_col.button("Finish", key=f"finish_set_{set_id}"):
                                self.sets.set_end_time(
                                    set_id,
                                    datetime.datetime.now().isoformat(
                                        timespec="seconds"
                                    ),
                                )
                            st.rerun()
                        del_col, up_col, down_col = st.columns(3)
                        if del_col.button("Delete", key=f"del_{set_id}"):
                            self._confirm_delete_set(set_id)
                            continue
                        if up_col.button("Move Up", key=f"move_up_{set_id}") and idx > 1:
                            pos = order.index(set_id)
                            if pos > 0:
                                order[pos - 1], order[pos] = order[pos], order[pos - 1]
                                self.sets.reorder_sets(exercise_id, order)
                                st.rerun()
                        if down_col.button("Move Down", key=f"move_down_{set_id}") and idx < len(order):
                            pos = order.index(set_id)
                            if pos < len(order) - 1:
                                order[pos], order[pos + 1] = order[pos + 1], order[pos]
                                self.sets.reorder_sets(exercise_id, order)
                                st.rerun()
                        if start_time:
                            st.write(self._format_time(start_time))
                        if end_time:
                            st.write(self._format_time(end_time))
                        if registered:
                            st.markdown(
                                "<div class='set-status'>registered</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        exp = st.expander(
                            f"Set {idx} - {reps}x{weight}kg RPE {rpe}", expanded=False
                        )
                        with exp:
                            st.markdown(
                                f"<div class='set-row {row_class}'>", unsafe_allow_html=True
                            )
                            cols = st.columns(16)
                            with cols[0]:
                                st.write(f"Set {idx}")
                        reps_val = cols[1].number_input(
                            "Reps",
                            min_value=1,
                            step=1,
                            value=int(reps),
                            key=f"reps_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        weight_val = cols[2].number_input(
                            f"Weight ({self.weight_unit})",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"weight_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"rpe_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        warm_chk = cols[4].checkbox(
                            "W",
                            value=bool(detail.get("warmup")),
                            key=f"warm_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        note_val = cols[5].text_input(
                            "Note",
                            value=detail.get("note") or "",
                            key=f"note_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        dur_default = 0.0
                        if start_time and end_time:
                            t0 = datetime.datetime.fromisoformat(start_time)
                            t1 = datetime.datetime.fromisoformat(end_time)
                            dur_default = (t1 - t0).total_seconds()
                        duration_val = cols[6].number_input(
                            "Duration (sec)",
                            min_value=0.0,
                            step=1.0,
                            value=dur_default,
                            key=f"duration_{set_id}",
                            on_change=self._update_set,
                            args=(set_id,),
                        )
                        cols[7].write(f"{detail['diff_reps']:+}")
                        cols[8].write(f"{detail['diff_weight']:+.1f}")
                        cols[9].write(f"{detail['diff_rpe']:+}")
                        if cols[10].button("Start", key=f"start_set_{set_id}"):
                            self.sets.set_start_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                            st.rerun()
                        if cols[11].button("Finish", key=f"finish_set_{set_id}"):
                            self.sets.set_end_time(
                                set_id,
                                datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                            st.rerun()
                        if cols[12].button("Delete", key=f"del_{set_id}"):
                            self._confirm_delete_set(set_id)
                            continue
                        if cols[13].button("Move Up", key=f"move_up_{set_id}") and idx > 1:
                            pos = order.index(set_id)
                            if pos > 0:
                                order[pos - 1], order[pos] = order[pos], order[pos - 1]
                                self.sets.reorder_sets(exercise_id, order)
                                st.rerun()
                        if cols[14].button("Move Down", key=f"move_down_{set_id}") and idx < len(order):
                            pos = order.index(set_id)
                            if pos < len(order) - 1:
                                order[pos], order[pos + 1] = order[pos + 1], order[pos]
                                self.sets.reorder_sets(exercise_id, order)
                                st.rerun()
                        if start_time:
                            cols[10].write(self._format_time(start_time))
                        if end_time:
                            cols[11].write(self._format_time(end_time))
                        if registered:
                            cols[15].markdown(
                                "<div class='set-status'>registered</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown("</div>", unsafe_allow_html=True)
            hist = self.stats.exercise_history(name)
            if hist:
                with st.expander("History (last 5)"):
                    self._responsive_table(hist[-5:][::-1])
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
            deleted = st.session_state.get("deleted_set")
            if deleted and deleted.get("exercise_id") == exercise_id:
                if st.button("Undo Delete", key=f"undo_{exercise_id}"):
                    det = st.session_state.pop("deleted_set")
                    new_id = self.sets.add(
                        det["exercise_id"],
                        int(det["reps"]),
                        float(det["weight"]),
                        int(det["rpe"]),
                        det["note"],
                        det["planned_set_id"],
                        int(det["diff_reps"]),
                        float(det["diff_weight"]),
                        int(det["diff_rpe"]),
                        det["warmup"],
                    )
                    if det["start_time"]:
                        self.sets.set_start_time(new_id, det["start_time"])
                    if det["end_time"]:
                        self.sets.set_end_time(new_id, det["end_time"])
                    st.success("Set restored")
                    st.rerun()
            st.markdown(
                f"<div id='ex_{exercise_id}_sets'></div>", unsafe_allow_html=True
            )
            with st.expander(
                "Add Set",
                expanded=st.session_state.pop(f"open_add_set_{exercise_id}", False),
            ):
                self._add_set_form(exercise_id, with_button=False)
            if st.button("Bulk Add Sets", key=f"bulk_{exercise_id}"):
                self._bulk_add_sets_dialog(exercise_id)
            if st.button("Warmup Plan", key=f"warmup_plan_{exercise_id}"):
                self._warmup_plan_dialog(exercise_id)
            if st.button("Reorder Sets", key=f"reorder_{exercise_id}"):
                self._reorder_sets_dialog(exercise_id)
            self._rest_timer()

    def _add_set_form(self, exercise_id: int, with_button: bool = True) -> None:
        qkey = f"qw_set_{exercise_id}"
        if qkey in st.session_state:
            st.session_state[f"new_weight_{exercise_id}"] = st.session_state.pop(qkey)
        reps = st.number_input(
            "Reps",
            min_value=1,
            step=1,
            key=f"new_reps_{exercise_id}",
        )
        errs = st.session_state.get(f"set_errors_{exercise_id}", {})
        if errs.get("reps"):
            st.error("Reps required")
        weight = st.number_input(
            f"Weight ({self.weight_unit})",
            min_value=0.0,
            step=0.5,
            key=f"new_weight_{exercise_id}",
        )
        if self.quick_weights:
            cols = st.columns(len(self.quick_weights))
            for idx, val in enumerate(self.quick_weights):
                label = self._format_weight(val)
                if cols[idx].button(label, key=f"qw_{exercise_id}_{idx}"):
                    st.session_state[qkey] = val
                    st.rerun()
        if errs.get("weight"):
            st.error("Weight required")
        rpe = st.selectbox(
            "RPE",
            options=list(range(11)),
            key=f"new_rpe_{exercise_id}",
        )
        note = st.text_input("Note", key=f"new_note_{exercise_id}")
        duration = st.number_input(
            "Duration (sec)",
            min_value=0.0,
            step=1.0,
            key=f"new_duration_{exercise_id}",
        )
        warmup = st.checkbox("Warmup", key=f"new_warmup_{exercise_id}")
        last = self.sets.fetch_for_exercise(exercise_id)
        if last:
            if st.button("Copy Last Set", key=f"copy_{exercise_id}"):
                l = last[-1]
                st.session_state[f"new_reps_{exercise_id}"] = int(l[1])
                st.session_state[f"new_weight_{exercise_id}"] = float(l[2])
                st.session_state[f"new_rpe_{exercise_id}"] = int(l[3])
        if with_button and st.button("Add Set", key=f"add_set_{exercise_id}"):
            errors = {}
            if reps < 1:
                errors["reps"] = "required"
            if weight <= 0:
                errors["weight"] = "required"
            if errors:
                st.session_state[f"set_errors_{exercise_id}"] = errors
            else:
                st.session_state.pop(f"set_errors_{exercise_id}", None)
                self._submit_set(exercise_id, reps, weight, rpe, note, duration, warmup)

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

    def _warmup_plan_dialog(self, exercise_id: int) -> None:
        def _content() -> None:
            tgt = st.number_input(
                "Target Weight (kg)",
                min_value=0.0,
                step=0.5,
                key=f"plan_tgt_{exercise_id}",
            )
            reps = st.number_input(
                "Target Reps", min_value=1, step=1, key=f"plan_reps_{exercise_id}"
            )
            count = st.number_input(
                "Warmup Sets",
                min_value=1,
                step=1,
                value=3,
                key=f"plan_cnt_{exercise_id}",
            )
            if st.button("Add", key=f"plan_add_{exercise_id}"):
                try:
                    plan = MathTools.warmup_plan(float(tgt), int(reps), int(count))
                    for r, w in plan:
                        self.sets.add(exercise_id, int(r), float(w), 6, warmup=True)
                        self.gamification.record_set(exercise_id, int(r), float(w), 6)
                    st.success(f"Added {len(plan)} sets")
                except ValueError as e:
                    st.warning(str(e))
                for key in [
                    f"plan_tgt_{exercise_id}",
                    f"plan_reps_{exercise_id}",
                    f"plan_cnt_{exercise_id}",
                ]:
                    st.session_state.pop(key, None)
            st.button("Close", key=f"plan_close_{exercise_id}")

        self._show_dialog("Warmup Plan", _content)

    def _reorder_sets_dialog(self, exercise_id: int) -> None:
        def _content() -> None:
            st.markdown("Drag sets to reorder and save")
            sets = self.sets.fetch_for_exercise(exercise_id)
            items = "".join(
                f"<li data-id='{sid}'>{i+1}: {r}x{self._format_weight(w)} RPE {rp}</li>"
                for i, (sid, r, w, rp, *_rest) in enumerate(sets)
            )
            html = f"""
            <ul id='order_{exercise_id}' class='order-list'>{items}</ul>
            <script src='https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js'></script>
            <script>
            const list = document.getElementById('order_{exercise_id}');
            if(list && !list.dataset.init){{
                list.dataset.init='1';
                new Sortable(list, {{animation:150}});
            }}
            function saveOrder(){{
                const ids = Array.from(list.children).map(c=>c.dataset.id).join(',');
                fetch('/exercises/{exercise_id}/set_order?order='+ids, {{method:'POST'}})
                    .then(()=>window.location.reload());
            }}
            </script>
            <button onclick='saveOrder()'>Save</button>
            """
            components.html(html, height=300)
            st.button("Close", key=f'reorder_close_{exercise_id}')

        self._show_dialog("Reorder Sets", _content)

    def _reorder_templates_dialog(self) -> None:
        def _content() -> None:
            st.markdown("Drag templates to reorder and save")
            templates = self.template_workouts.fetch_all()
            items = "".join(
                f"<li data-id='{tid}'>{i+1}: {name}</li>"
                for i, (tid, name, _t) in enumerate(templates)
            )
            html = f"""
            <ul id='tpl_order' class='order-list'>{items}</ul>
            <script src='https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js'></script>
            <script>
            const list = document.getElementById('tpl_order');
            if(list && !list.dataset.init){{
                list.dataset.init='1';
                new Sortable(list, {{animation:150}});
            }}
            function saveOrder(){{
                const ids = Array.from(list.children).map(c=>c.dataset.id).join(',');
                fetch('/templates/order?order='+ids, {{method:'POST'}})
                    .then(()=>window.location.reload());
            }}
            </script>
            <button onclick='saveOrder()'>Save</button>
            """
            components.html(html, height=300)
            st.button("Close", key='tpl_order_close')

        self._show_dialog("Reorder Templates", _content)

    def _submit_set(
        self,
        exercise_id: int,
        reps: int,
        weight: float,
        rpe: int,
        note: str,
        duration: float,
        warmup: bool = False,
    ) -> None:
        """Create a new set and record gamification metrics."""
        sid = self.sets.add(
            exercise_id,
            int(reps),
            float(weight) / 2.20462 if self.weight_unit == "lb" else float(weight),
            int(rpe),
            note or None,
            warmup=warmup,
        )
        st.session_state.flash_set = sid
        st.session_state.rest_start = time.time()
        if duration > 0:
            self.sets.set_duration(sid, float(duration))
        self.gamification.record_set(exercise_id, int(reps), float(weight), int(rpe))
        st.session_state.pop(f"new_reps_{exercise_id}", None)
        st.session_state.pop(f"new_weight_{exercise_id}", None)
        st.session_state.pop(f"new_rpe_{exercise_id}", None)
        st.session_state.pop(f"new_duration_{exercise_id}", None)
        st.session_state.pop(f"new_warmup_{exercise_id}", None)
        st.session_state.scroll_to = f"ex_{exercise_id}_sets"
        st.session_state[f"open_add_set_{exercise_id}"] = True
        st.rerun()

    def _update_set(self, set_id: int) -> None:
        """Update set values based on current widget state."""
        reps_val = st.session_state.get(f"reps_{set_id}")
        weight_val = st.session_state.get(f"weight_{set_id}")
        rpe_val = st.session_state.get(f"rpe_{set_id}")
        note_val = st.session_state.get(f"note_{set_id}", "")
        dur_val = st.session_state.get(f"duration_{set_id}", 0.0)
        warm_val = st.session_state.get(f"warm_{set_id}")
        weight = float(weight_val)
        if self.weight_unit == "lb":
            weight /= 2.20462
        self.sets.update(set_id, int(reps_val), weight, int(rpe_val), warm_val)
        self.sets.update_note(set_id, note_val or None)
        if dur_val and float(dur_val) > 0:
            self.sets.set_duration(set_id, float(dur_val))
        st.rerun()

    def _update_workout_type(self, workout_id: int) -> None:
        val = st.session_state.get(f"type_select_{workout_id}")
        self.workouts.set_training_type(workout_id, val)
        st.rerun()

    def _update_workout_notes(self, workout_id: int) -> None:
        val = st.session_state.get(f"workout_notes_{workout_id}", "")
        self.workouts.set_note(workout_id, val or None)
        st.rerun()

    def _update_workout_location(self, workout_id: int) -> None:
        val = st.session_state.get(f"workout_location_{workout_id}", "")
        self.workouts.set_location(workout_id, val or None)
        st.rerun()

    def _update_workout_rating(self, workout_id: int) -> None:
        val = st.session_state.get(f"rating_{workout_id}")
        self.workouts.set_rating(workout_id, int(val) if val is not None else None)
        st.rerun()

    def _update_workout_tags(self, workout_id: int) -> None:
        selected = st.session_state.get(f"tags_sel_{workout_id}", [])
        name_map = {n: tid for tid, n in self.tags_repo.fetch_all()}
        ids = [name_map[n] for n in selected]
        self.tags_repo.set_tags(workout_id, ids)
        st.rerun()

    def _update_planned_workout(self, plan_id: int) -> None:
        date_val = st.session_state.get(f"plan_edit_{plan_id}")
        type_val = st.session_state.get(f"plan_type_{plan_id}")
        if date_val:
            self.planned_workouts.update_date(plan_id, date_val.isoformat())
        if type_val:
            self.planned_workouts.set_training_type(plan_id, type_val)
        st.rerun()

    def _update_planned_set(self, set_id: int) -> None:
        reps_val = st.session_state.get(f"plan_reps_{set_id}")
        weight_val = st.session_state.get(f"plan_weight_{set_id}")
        rpe_val = st.session_state.get(f"plan_rpe_{set_id}")
        self.planned_sets.update(set_id, int(reps_val), float(weight_val), int(rpe_val))
        st.rerun()

    def _update_template_set(self, set_id: int) -> None:
        reps_val = st.session_state.get(f"tmpl_reps_{set_id}")
        weight_val = st.session_state.get(f"tmpl_w_{set_id}")
        rpe_val = st.session_state.get(f"tmpl_rpe_{set_id}")
        self.template_sets.update(
            set_id, int(reps_val), float(weight_val), int(rpe_val)
        )
        st.rerun()

    def _update_equipment(self, original: str) -> None:
        new_name = st.session_state.get(f"edit_name_{original}")
        new_type = st.session_state.get(f"edit_type_{original}")
        muscles = st.session_state.get(f"edit_mus_{original}", [])
        try:
            self.equipment.update(original, new_type, muscles, new_name)
        except ValueError as e:
            st.warning(str(e))
        st.rerun()

    def _confirm_delete_set(self, set_id: int) -> None:
        def _content() -> None:
            st.write(f"Delete set {set_id}?")
            cols = st.columns(2)
            if cols[0].button("Yes", key=f"yes_{set_id}"):
                ex_id = self.sets.fetch_exercise_id(set_id)
                detail = self.sets.fetch_detail(set_id)
                detail["exercise_id"] = ex_id
                st.session_state.deleted_set = detail
                self.sets.remove(set_id)
                st.rerun()
            if cols[1].button("No", key=f"no_{set_id}"):
                st.rerun()

        self._show_dialog("Confirm Delete", _content)

    def _confirm_delete_workout(self, workout_id: int) -> None:
        def _content() -> None:
            st.write(f"Delete workout {workout_id}?")
            cols = st.columns(2)
            if cols[0].button("Yes", key=f"yes_w_{workout_id}"):
                self.workouts.delete(workout_id)
                if st.session_state.get("selected_workout") == workout_id:
                    st.session_state.selected_workout = None
                st.rerun()
            if cols[1].button("No", key=f"no_w_{workout_id}"):
                st.rerun()

        self._show_dialog("Confirm Delete", _content)

    def _handle_context_action(self, params: dict[str, str]) -> None:
        action = params.pop("ctx_action", None)
        wid = params.pop("ctx_id", None)
        if action and wid:
            if action == "delete":
                self._confirm_delete_workout(int(wid))
            elif action == "copy":
                tid = self.planner.copy_workout_to_template(int(wid))
                st.success(f"Template {tid} created")
            st.experimental_set_query_params(**params)

    def _confirm_delete_exercise(self, exercise_id: int) -> None:
        def _content() -> None:
            st.write(f"Delete exercise {exercise_id}?")
            cols = st.columns(2)
            if cols[0].button("Yes", key=f"yes_e_{exercise_id}"):
                self.exercises.remove(exercise_id)
                st.rerun()
            if cols[1].button("No", key=f"no_e_{exercise_id}"):
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
                            del_col, _ = st.columns(2)
                            if del_col.button("Delete", key=f"del_plan_set_{set_id}"):
                                self.planned_sets.remove(set_id)
                                continue
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"plan_reps_{set_id}",
                                on_change=self._update_planned_set,
                                args=(set_id,),
                            )
                            weight_val = st.number_input(
                                "Weight (kg)",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"plan_weight_{set_id}",
                                on_change=self._update_planned_set,
                                args=(set_id,),
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"plan_rpe_{set_id}",
                                on_change=self._update_planned_set,
                                args=(set_id,),
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
                            on_change=self._update_planned_set,
                            args=(set_id,),
                        )
                        weight_val = cols[2].number_input(
                            "Weight (kg)",
                            min_value=0.0,
                            step=0.5,
                            value=float(weight),
                            key=f"plan_weight_{set_id}",
                            on_change=self._update_planned_set,
                            args=(set_id,),
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"plan_rpe_{set_id}",
                            on_change=self._update_planned_set,
                            args=(set_id,),
                        )
                        if cols[4].button("Delete", key=f"del_plan_set_{set_id}"):
                            self.planned_sets.remove(set_id)
                            continue
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
                all_templates = self.template_workouts.fetch_all()
                favs = self.favorite_templates_repo.fetch_all()
                fav_templates = [t for t in all_templates if t[0] in favs]
                other_templates = [t for t in all_templates if t[0] not in favs]
                ordered = fav_templates + sorted(other_templates, key=lambda r: r[1])
                templates = {str(t[0]): t[1] for t in ordered}
                add_choice = st.selectbox(
                    "Add Favorite",
                    [""] + list(templates.keys()),
                    format_func=lambda x: "" if x == "" else templates[x],
                    key="fav_tpl_add_choice",
                )
                if st.button("Add Favorite", key="fav_tpl_add_btn") and add_choice:
                    self.favorite_templates_repo.add(int(add_choice))
                    st.rerun()
                if st.button("Reorder Templates", key="reorder_templates_btn"):
                    self._reorder_templates_dialog()
            with st.expander("Create New Template"):
                name = st.text_input("Name", key="tmpl_name")
                t_type = st.selectbox(
                    "Training Type",
                    self.training_options,
                    index=self.training_options.index("strength"),
                    key="tmpl_type",
                )
                if st.button("Create Template") and name:
                    tid = self.template_workouts.create(name, t_type)
                    st.session_state.selected_template = tid
            with st.expander("Existing Templates", expanded=True):
                all_templates = self.template_workouts.fetch_all()
                favs = self.favorite_templates_repo.fetch_all()
                fav_templates = [t for t in all_templates if t[0] in favs]
                other_templates = [t for t in all_templates if t[0] not in favs]
                templates = fav_templates + sorted(other_templates, key=lambda r: r[1])
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
                                self.training_options,
                                index=self.training_options.index(t_type),
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
                for idx, (sid, reps, weight, rpe) in enumerate(sets, start=1):
                    if st.session_state.is_mobile:
                        with st.expander(f"Set {idx}"):
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
                            del_col, _ = st.columns(2)
                            if del_col.button("Delete", key=f"tmpl_del_set_{sid}"):
                                self.template_sets.remove(sid)
                                continue
                            reps_val = st.number_input(
                                "Reps",
                                min_value=1,
                                step=1,
                                value=int(reps),
                                key=f"tmpl_reps_{sid}",
                                on_change=self._update_template_set,
                                args=(sid,),
                            )
                            weight_val = st.number_input(
                                "Weight",
                                min_value=0.0,
                                step=0.5,
                                value=float(weight),
                                key=f"tmpl_w_{sid}",
                                on_change=self._update_template_set,
                                args=(sid,),
                            )
                            rpe_val = st.selectbox(
                                "RPE",
                                options=list(range(11)),
                                index=int(rpe),
                                key=f"tmpl_rpe_{sid}",
                                on_change=self._update_template_set,
                                args=(sid,),
                            )
                    else:
                        cols = st.columns(5)
                        cols[0].write(f"Set {idx}")
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
                            on_change=self._update_template_set,
                            args=(sid,),
                        )
                        rpe_val = cols[3].selectbox(
                            "RPE",
                            options=list(range(11)),
                            index=int(rpe),
                            key=f"tmpl_rpe_{sid}",
                            on_change=self._update_template_set,
                            args=(sid,),
                        )
                        if cols[4].button("Delete", key=f"tmpl_del_set_{sid}"):
                            self.template_sets.remove(sid)
                            continue
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
        self._tab_tips(
            [
                "Filter by muscle or equipment to locate exercises quickly.",
                "Link variants so progress is tracked across similar movements.",
            ]
        )
        with st.expander("Favorites", expanded=False):
            self._favorites_library()
        if st.query_params.get("tab") == "library":
            with st.expander("Templates", expanded=False):
                self._template_section()
                if st.session_state.get("selected_template") is not None:
                    self._template_exercise_section()
        else:
            with st.expander("Templates", expanded=False):
                st.write(" ")
        with st.expander("Equipment", expanded=False):
            self._equipment_library()
        with st.expander("Exercises", expanded=True):
            self._exercise_catalog_library()

    def _favorites_library(self) -> None:
        st.header("Favorite Exercises")
        favs = self.favorites_repo.fetch_all()
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

    def _equipment_library(self) -> None:
        muscles = self.muscles_repo.fetch_all()
        recent_mus = self.stats.recent_muscles()
        muscles = list(dict.fromkeys(recent_mus + muscles))
        types = ["" ] + self.equipment.fetch_types()
        if st.session_state.is_mobile:
            with st.expander("Filters", expanded=True):
                sel_type = st.multiselect("Type", types, key="lib_eq_type")
                prefix = st.text_input("Name Contains", key="lib_eq_prefix")
                mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
                if st.button("Reset Filters", key="lib_eq_reset"):
                    self._reset_equipment_filters()
            names = self.equipment.fetch_names(
                sel_type if sel_type else None,
                prefix or None,
                mus_filter or None,
            )
            recent_eq = self.stats.recent_equipment()
            names = list(dict.fromkeys(recent_eq + names))
            with st.expander("Equipment List", expanded=False):
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
                sel_type = st.multiselect("Type", types, key="lib_eq_type")
                prefix = st.text_input("Name Contains", key="lib_eq_prefix")
                mus_filter = st.multiselect("Muscles", muscles, key="lib_eq_mus")
                if st.button("Reset Filters", key="lib_eq_reset"):
                    self._reset_equipment_filters()
            names = self.equipment.fetch_names(
                sel_type if sel_type else None,
                prefix or None,
                mus_filter or None,
            )
            recent_eq = self.stats.recent_equipment()
            names = list(dict.fromkeys(recent_eq + names))
            with l_col.expander("Equipment List", expanded=False):
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
        recent_mus = self.stats.recent_muscles()
        muscles = list(dict.fromkeys(recent_mus + muscles))
        hide_pre = st.checkbox(
            "Hide Preconfigured Exercises",
            value=self.settings_repo.get_bool("hide_preconfigured_exercises", False),
        )
        self.settings_repo.set_bool("hide_preconfigured_exercises", hide_pre)
        if st.session_state.is_mobile:
            sel_groups = st.multiselect("Muscle Groups", groups, key="lib_ex_groups")
            sel_mus = st.multiselect("Muscles", muscles, key="lib_ex_mus")
            eq_names = self.equipment.fetch_names()
            recent_eq = self.stats.recent_equipment()
            eq_names = list(dict.fromkeys(recent_eq + eq_names))
            sel_eq = st.selectbox("Equipment", ["" ] + eq_names, key="lib_ex_eq")
            name_filter = st.text_input("Name Contains", key="lib_ex_prefix")
            if st.button("Reset Filters", key="lib_ex_reset"):
                self._reset_exercise_filters()
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
                    recent_eq = self.stats.recent_equipment()
                    eq_names = list(dict.fromkeys(recent_eq + eq_names))
                    sel_eq = st.selectbox("Equipment", ["" ] + eq_names, key="lib_ex_eq")
                    name_filter = st.text_input("Name Contains", key="lib_ex_prefix")
                    if st.button("Reset Filters", key="lib_ex_reset"):
                        self._reset_exercise_filters()
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

        with st.expander("Link Variants"):
            names = self.exercise_catalog.fetch_names(None, None, None, None)
            col1, col2 = st.columns(2)
            with col1:
                base_ex = st.selectbox("Exercise", names, key="var_base")
            with col2:
                var_ex = st.selectbox("Variant", names, key="var_variant")
            if st.button("Link Variant"):
                self.exercise_variants_repo.link(base_ex, var_ex)
                st.success("Linked")

        if st.session_state.is_mobile:
            with st.expander("Add Custom Exercise"):
                group = st.selectbox("Muscle Group", groups, key="cust_ex_group")
                name = st.text_input("Exercise Name", key="cust_ex_name")
                variants = st.text_input("Variants", key="cust_ex_variants")
                eq_sel = st.multiselect("Equipment", equipment_names, key="cust_ex_eq")
                match_muscles = st.checkbox(
                    "Muscles Like Equipment", key="cust_ex_match"
                )
                primary_sel = st.selectbox(
                    "Primary Muscle", muscles, key="cust_ex_primary"
                )
                secondary_sel = st.multiselect("Secondary", muscles, key="cust_ex_sec")
                tertiary_sel = st.multiselect("Tertiary", muscles, key="cust_ex_ter")
                other_sel = st.multiselect("Other", muscles, key="cust_ex_other")
                if st.button("Add Exercise", key="cust_ex_add"):
                    if name:
                        try:
                            if match_muscles and eq_sel:
                                muscs: list[str] = []
                                for eq in eq_sel:
                                    muscs.extend(self.equipment.fetch_muscles(eq))
                                uniq = list(dict.fromkeys(muscs))
                                primary = uniq[0]
                                secondary = "|".join(uniq[1:])
                                tertiary = ""
                                other = ""
                            else:
                                primary = primary_sel
                                secondary = "|".join(secondary_sel)
                                tertiary = "|".join(tertiary_sel)
                                other = "|".join(other_sel)
                            self.exercise_catalog.add(
                                group,
                                name,
                                variants,
                                "|".join(eq_sel),
                                primary,
                                secondary,
                                tertiary,
                                other,
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
                        with st.expander("Variants", expanded=False):
                            current_vars = self.exercise_variants_repo.fetch_variants(
                                name
                            )
                            for v in current_vars:
                                c1, c2 = st.columns(2)
                                c1.write(v)
                                if c2.button("Unlink", key=f"unlink_var_{name}_{v}"):
                                    self.exercise_variants_repo.unlink(name, v)
                                    st.rerun()
                            add_v = st.selectbox(
                                "Add Variant", [""] + names, key=f"add_var_{name}"
                            )
                            if (
                                st.button("Add Variant", key=f"add_var_btn_{name}")
                                and add_v
                            ):
                                self.exercise_variants_repo.link(name, add_v)
                                st.rerun()
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
                match_muscles = st.checkbox(
                    "Muscles Like Equipment", key="cust_ex_match"
                )
                primary_sel = st.selectbox(
                    "Primary Muscle", muscles, key="cust_ex_primary"
                )
                secondary_sel = st.multiselect("Secondary", muscles, key="cust_ex_sec")
                tertiary_sel = st.multiselect("Tertiary", muscles, key="cust_ex_ter")
                other_sel = st.multiselect("Other", muscles, key="cust_ex_other")
                if st.button("Add Exercise", key="cust_ex_add"):
                    if name:
                        try:
                            if match_muscles and eq_sel:
                                muscs: list[str] = []
                                for eq in eq_sel:
                                    muscs.extend(self.equipment.fetch_muscles(eq))
                                uniq = list(dict.fromkeys(muscs))
                                primary = uniq[0]
                                secondary = "|".join(uniq[1:])
                                tertiary = ""
                                other = ""
                            else:
                                primary = primary_sel
                                secondary = "|".join(secondary_sel)
                                tertiary = "|".join(tertiary_sel)
                                other = "|".join(other_sel)
                            self.exercise_catalog.add(
                                group,
                                name,
                                variants,
                                "|".join(eq_sel),
                                primary,
                                secondary,
                                tertiary,
                                other,
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
                        with st.expander("Variants", expanded=False):
                            current_vars = self.exercise_variants_repo.fetch_variants(
                                name
                            )
                            for v in current_vars:
                                c1, c2 = st.columns(2)
                                c1.write(v)
                                if c2.button("Unlink", key=f"unlink_var_{name}_{v}"):
                                    self.exercise_variants_repo.unlink(name, v)
                                    st.rerun()
                            add_v = st.selectbox(
                                "Add Variant", [""] + names, key=f"add_var_{name}"
                            )
                            if (
                                st.button("Add Variant", key=f"add_var_btn_{name}")
                                and add_v
                            ):
                                self.exercise_variants_repo.link(name, add_v)
                                st.rerun()
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
            all_workouts = {
                str(w[0]): w[1]
                for w in sorted(self.workouts.fetch_all_workouts(), key=lambda r: r[1])
            }
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
            chip_cols = st.columns(3)
            if chip_cols[0].button("Last 7d", key="hist_7d"):
                st.session_state.hist_start = datetime.date.today() - datetime.timedelta(days=7)
                st.session_state.hist_end = datetime.date.today()
                st.rerun()
            if chip_cols[1].button("Last 30d", key="hist_30d"):
                st.session_state.hist_start = datetime.date.today() - datetime.timedelta(days=30)
                st.session_state.hist_end = datetime.date.today()
                st.rerun()
            if chip_cols[2].button("Last 90d", key="hist_90d"):
                st.session_state.hist_start = datetime.date.today() - datetime.timedelta(days=90)
                st.session_state.hist_end = datetime.date.today()
                st.rerun()
            if st.button("Reset", key="hist_reset"):
                st.session_state.hist_start = (
                    datetime.date.today() - datetime.timedelta(days=30)
                )
                st.session_state.hist_end = datetime.date.today()
                st.session_state.hist_type = ""
                st.session_state.hist_tags = []
                st.rerun()
            hist_types = [""] + self.training_options
            ttype = st.selectbox(
                "Training Type",
                hist_types,
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
        pr_dates = {r["date"] for r in self.stats.personal_records()}
        for wid, date, _s, _e, training_type, *_ in workouts:
            badge = f"<span class='training-badge tt-{training_type}'>{training_type}</span>"
            label = f"{date} {badge}"
            if date in pr_dates:
                label = f"**{label}**"
            with st.expander(label, expanded=False):
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
        records = {
            (r["exercise"], r["date"], r["reps"], r["weight"]): True
            for r in self.stats.personal_records()
        }
        w_date = self.workouts.fetch_detail(workout_id)[1]

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
                        if (name, w_date, reps, weight) in records:
                            st.markdown(
                                f"<span style='color: var(--accent-color); font-weight:bold'>{line} - PR</span>",
                                unsafe_allow_html=True,
                            )
                        else:
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
            self._responsive_table(summary)
            daily = self.stats.daily_volume(start_str, end_str)
            if daily:
                self._line_chart(
                    {"Volume": [d["volume"] for d in daily]},
                    [d["date"] for d in daily],
                )
            equip_stats = self.stats.equipment_usage(start_str, end_str)
            self._responsive_table(equip_stats)
            eff_stats = self.stats.session_efficiency(start_str, end_str)
            if eff_stats:
                with st.expander("Session Efficiency", expanded=False):
                    self._responsive_table(eff_stats)
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
                vel_hist = self.stats.velocity_history(ex_choice, start_str, end_str)
                rel_power = self.stats.relative_power_history(ex_choice, start_str, end_str)

                charts: list[Callable[[], None]] = []
                if prog:
                    charts.append(lambda prog=prog: self._line_chart(
                        {"1RM": [p["est_1rm"] for p in prog]},
                        [p["date"] for p in prog],
                    ))
                if vel_hist:
                    charts.append(lambda vel_hist=vel_hist: self._line_chart(
                        {"Velocity": [v["velocity"] for v in vel_hist]},
                        [v["date"] for v in vel_hist],
                    ))
                if rel_power:
                    charts.append(lambda rel_power=rel_power: self._line_chart(
                        {"Power/Weight": [p["relative_power"] for p in rel_power]},
                        [p["date"] for p in rel_power],
                    ))
                self._chart_carousel(charts, "prog_car")
                self._progress_forecast_section(ex_choice)
            self._volume_forecast_section(start_str, end_str)
        with rec_tab:
            records = self.stats.personal_records(
                ex_choice if ex_choice else None,
                start_str,
                end_str,
            )
            if records:
                self._responsive_table(records)
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
        with st.expander("Progress Forecast", expanded=False):
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
        with st.expander("Volume Forecast", expanded=False):
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
        if st.button("Show Tutorial", key="insights_tut"):
            st.session_state.show_analytics_tutorial = True
        if st.session_state.get("show_analytics_tutorial"):
            self._analytics_tutorial_dialog()
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

    def _wellness_tab(self) -> None:
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
            qcol1, qcol2 = st.columns(2)
            if qcol1.button("Last Week", key="rep_last_week"):
                st.session_state.rep_start = (
                    datetime.date.today() - datetime.timedelta(days=7)
                )
                st.session_state.rep_end = datetime.date.today()
                st.rerun()
            if qcol2.button("Last Month", key="rep_last_month"):
                st.session_state.rep_start = (
                    datetime.date.today() - datetime.timedelta(days=30)
                )
                st.session_state.rep_end = datetime.date.today()
                st.rerun()
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
                self._responsive_table(data[:5])
        with st.expander("Exercise Frequency", expanded=True):
            freq = self.stats.exercise_frequency(None, start_str, end_str)
            if freq:
                self._responsive_table(freq)
        with st.expander("Equipment Usage", expanded=True):
            eq_stats = self.stats.equipment_usage(start_str, end_str)
            if eq_stats:
                self._responsive_table(eq_stats)
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
                self._responsive_table(wvc)
                self._line_chart(
                    {"Change": [v["change"] for v in wvc]},
                    [v["week"] for v in wvc],
                )
        with st.expander("Session Duration", expanded=False):
            duration = self.stats.session_duration(start_str, end_str)
            if duration:
                self._responsive_table(duration)
                self._line_chart(
                    {"Duration": [d["duration"] for d in duration]},
                    [d["date"] for d in duration],
                )
        with st.expander("Session Density", expanded=False):
            density = self.stats.session_density(start_str, end_str)
            if density:
                self._responsive_table(density)
                self._line_chart(
                    {"Density": [d["density"] for d in density]},
                    [d["date"] for d in density],
                )
        with st.expander("Set Pace", expanded=False):
            pace = self.stats.set_pace(start_str, end_str)
            if pace:
                self._responsive_table(pace)
                self._line_chart(
                    {"Pace": [p["pace"] for p in pace]},
                    [p["date"] for p in pace],
                )
        with st.expander("Average Rest Times", expanded=False):
            rests = self.stats.rest_times(start_str, end_str)
            if rests:
                self._responsive_table(rests)
                self._bar_chart(
                    {"Rest": [r["avg_rest"] for r in rests]},
                    [str(r["workout_id"]) for r in rests],
                )
        with st.expander("Exercise Diversity", expanded=False):
            div = self.stats.exercise_diversity(start_str, end_str)
            if div:
                self._responsive_table(div)
                self._line_chart(
                    {"Diversity": [d["diversity"] for d in div]},
                    [d["date"] for d in div],
                )
        with st.expander("Time Under Tension", expanded=False):
            tut = self.stats.time_under_tension(start_str, end_str)
            if tut:
                self._responsive_table(tut)
                self._line_chart(
                    {"TUT": [t["tut"] for t in tut]},
                    [t["date"] for t in tut],
                )
        with st.expander("Location Summary", expanded=False):
            loc_stats = self.stats.location_summary(start_str, end_str)
            if loc_stats:
                self._responsive_table(loc_stats)
        with st.expander("Training Type Summary", expanded=False):
            tt_stats = self.stats.training_type_summary(start_str, end_str)
            if tt_stats:
                self._responsive_table(tt_stats)
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
        streak = self.gamification.workout_streak()
        with st.expander("Streak", expanded=True):
            self._metric_grid(
                [
                    ("Current Streak", streak["current"]),
                    ("Record Streak", streak["record"]),
                ]
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
                self._responsive_table(display)

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
                    self._responsive_table(
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
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df["weekday"] = df["date"].dt.day_name()
            df["week"] = df["date"].dt.isocalendar().week
            chart = (
                alt.Chart(df)
                .mark_rect()
                .encode(
                    x=alt.X(
                        "weekday", sort=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    ),
                    y="week:O",
                    color=alt.condition(
                        "datum.planned",
                        alt.value("orange"),
                        alt.value("steelblue"),
                    ),
                    tooltip=["date", "type", "planned"],
                )
                .interactive()
            )
            st.markdown("<div id='calendar_chart'></div>", unsafe_allow_html=True)
            st.altair_chart(chart, use_container_width=True)
            components.html(
                "<script>document.getElementById('calendar_chart').scrollIntoView({behavior:'auto',block:'center'});</script>",
                height=0,
            )

    def _mini_calendar_widget(self) -> None:
        start = datetime.date.today()
        end = start + datetime.timedelta(days=30)
        rows = self.planned_workouts.fetch_all(start.isoformat(), end.isoformat())
        if not rows:
            st.info("No upcoming plans")
            return
        df = pd.DataFrame(
            [{"date": d, "type": t} for _pid, d, t in rows]
        )
        df["date"] = pd.to_datetime(df["date"])
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(x="date:T", y=alt.value(5), tooltip=["date", "type"])
        )
        st.altair_chart(chart, use_container_width=True)

    def _goals_tab(self) -> None:
        st.header("Goals")
        overview_tab, manage_tab = st.tabs(["Overview", "Manage"])
        with manage_tab:
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
            with st.expander("Existing Goals", expanded=False):
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
        with overview_tab:
            rows = self.goals_repo.fetch_all()
            if not rows:
                st.info("No goals defined.")
            else:
                metrics = []
                for _gid, exn, gname, gval, gunit, sdate, _tdate, _ach in rows:
                    prog = self.stats.progression(exn, sdate)
                    current = prog[-1]["est_1rm"] if prog else 0
                    pct = (current / gval * 100) if gval else 0
                    metrics.append((gname, f"{pct:.1f}%"))
                self._metric_grid(metrics)

    def _settings_tab(self) -> None:
        st.header("Settings")
        self._tab_tips(
            [
                "Update your personal data for precise calculations.",
                "Manage aliases and equipment lists to streamline logging.",
            ]
        )
        if "delete_target" not in st.session_state:
            st.session_state.delete_target = None

        with st.expander("Data Management", expanded=True):
            if st.button("Delete All Logged and Planned Workouts"):
                st.session_state.delete_target = "all"
            if st.button("Delete All Logged Workouts"):
                st.session_state.delete_target = "logged"
            if st.button("Delete All Planned Workouts"):
                st.session_state.delete_target = "planned"
            with open(self.workouts._db_path, "rb") as f:
                st.download_button(
                    "Backup Database",
                    f.read(),
                    file_name="backup.db",
                    mime="application/octet-stream",
                )
            up = st.file_uploader("Restore Backup", type=["db"], key="restore_db")
            if up and st.button("Restore", key="restore_btn"):
                Path(self.workouts._db_path).write_bytes(up.getvalue())
                st.success("Database restored")

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
            tag_tab,
            eq_tab,
            cust_tab,
            mus_tab,
            ex_tab,
            bw_tab,
            hr_tab,
            auto_tab,
        ) = st.tabs(
            [
                "General",
                "Workout Tags",
                "Equipment",
                "Exercise Management",
                "Muscles",
                "Exercise Aliases",
                "Body Weight Logs",
                "Heart Rate Logs",
                "Autoplanner Status",
            ]
        )

        with gen_tab:
            st.header("General Settings")
            with st.expander("Display Settings", expanded=True):
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
                themes = sorted(["light", "dark"])
                theme_opt = st.selectbox(
                    "Theme",
                    themes,
                    index=themes.index(self.theme),
                )
                auto_dark = st.checkbox(
                    "Automatic Dark Mode",
                    value=self.auto_dark_mode,
                    help="Match theme to system preference",
                )
                colors = ["red", "blue", "green", "purple", "colorblind"]
                color_opt = st.selectbox(
                    "Color Theme",
                    colors,
                    index=colors.index(self.color_theme),
                )
                avatar_file = st.file_uploader("Avatar", type=["png", "jpg"], key="avatar_upload")
                current_avatar = self.settings_repo.get_text("avatar", "")
                if current_avatar and Path(current_avatar).exists():
                    st.image(current_avatar, width=100)
                unit_opt = st.selectbox(
                    "Weight Unit",
                    ["kg", "lb"],
                    index=["kg", "lb"].index(self.weight_unit),
                )
                time_fmt_opt = st.selectbox(
                    "Time Format",
                    ["24h", "12h"],
                    index=["24h", "12h"].index(self.time_format),
                )
                compact = st.checkbox(
                    "Compact Mode",
                    value=self.compact_mode,
                )
                large_font = st.checkbox(
                    "Large Font Mode",
                    value=self.large_font,
                )
                side_nav_opt = st.checkbox(
                    "Enable Side Navigation",
                    value=self.side_nav,
                )
                sb_width = st.slider(
                    "Sidebar Width (rem)",
                    12.0,
                    30.0,
                    value=self.sidebar_width,
                    step=1.0,
                )
                show_onboard_opt = st.checkbox(
                    "Show Onboarding Wizard",
                    value=self.show_onboarding,
                )
                auto_open_opt = st.checkbox(
                    "Auto-Open Last Workout",
                    value=self.auto_open_last_workout,
                )
                add_key_in = st.text_input(
                    "Add Set Hotkey",
                    value=self.add_set_key,
                    max_chars=1,
                )
                tab_keys_in = st.text_input(
                    "Tab Hotkeys",
                    value=self.tab_keys,
                    help="Comma separated keys for Workouts, Library, Progress, Settings",
                )
                qw_in = st.text_input(
                    "Quick Add Weights",
                    value=",".join(str(int(w)) for w in self.quick_weights),
                    help="Comma separated weight values",
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
                if st.button("Train RPE Model", key="train_rpe_btn"):
                    rows = self.sets.fetch_all(
                        "SELECT id, exercise_id, reps, weight, rpe FROM sets ORDER BY id;"
                    )
                    progress = st.progress(0.0)
                    total = len(rows)
                    prev: dict[int, int] = {}
                    for i, (sid, ex_id, reps, weight, rpe) in enumerate(rows, start=1):
                        name = self.exercises.fetch_detail(ex_id)[1]
                        prev_rpe = prev.get(ex_id, rpe)
                        self.ml_service.train(name, int(reps), float(weight), int(rpe), prev_rpe)
                        prev[ex_id] = int(rpe)
                        progress.progress(i / total)
                    st.success("Model trained")
            with st.expander("Integrations", expanded=True):
                if st.button("Git Pull"):
                    try:
                        output = GitTools.git_pull("~/thebuilder")
                        st.code(output)
                        st.success("Repository updated")
                    except Exception as e:
                        st.warning(str(e))
            if st.button("Save General Settings"):
                progress = st.progress(0.0)
                self.settings_repo.set_float("body_weight", bw)
                self.settings_repo.set_float("height", height)
                self.settings_repo.set_float("months_active", ma)
                self.settings_repo.set_text("theme", theme_opt)
                self.settings_repo.set_text("color_theme", color_opt)
                self.settings_repo.set_bool("auto_dark_mode", auto_dark)
                self.theme = theme_opt
                self.color_theme = color_opt
                self.auto_dark_mode = auto_dark
                self._apply_theme()
                if avatar_file is not None:
                    out = Path("avatar.png")
                    out.write_bytes(avatar_file.getvalue())
                    self.settings_repo.set_text("avatar", str(out))
                self.settings_repo.set_text("weight_unit", unit_opt)
                self.settings_repo.set_text("time_format", time_fmt_opt)
                self.weight_unit = unit_opt
                self.time_format = time_fmt_opt
                self.settings_repo.set_bool("compact_mode", compact)
                self.compact_mode = compact
                self.settings_repo.set_bool("large_font_mode", large_font)
                self.large_font = large_font
                self.settings_repo.set_bool("side_nav", side_nav_opt)
                self.side_nav = side_nav_opt
                self.settings_repo.set_bool("show_onboarding", show_onboard_opt)
                self.show_onboarding = show_onboard_opt
                self.settings_repo.set_bool("auto_open_last_workout", auto_open_opt)
                self.auto_open_last_workout = auto_open_opt
                self.settings_repo.set_text("hotkey_add_set", add_key_in or 'a')
                self.settings_repo.set_text("hotkey_tab_keys", tab_keys_in or '1,2,3,4')
                self.settings_repo.set_text("quick_weights", qw_in)
                self.add_set_key = add_key_in or 'a'
                self.tab_keys = tab_keys_in or '1,2,3,4'
                self.quick_weights = [float(v) for v in qw_in.split(',') if v]
                self.settings_repo.set_float("sidebar_width", sb_width)
                self.sidebar_width = sb_width
                self._inject_responsive_css()
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
                progress.progress(1.0)
                st.success("Settings saved")

        with eq_tab:
            st.header("Equipment Management")
            hide_pre = st.checkbox(
                "Hide Preconfigured Equipment",
                value=self.settings_repo.get_bool(
                    "hide_preconfigured_equipment", False
                ),
            )
            self.settings_repo.set_bool("hide_preconfigured_equipment", hide_pre)
            with st.expander("Add Equipment Type"):
                new_type = st.text_input("Type Name", key="new_eq_type")
                if st.button("Add Type"):
                    if new_type:
                        try:
                            self.equipment.types.add(new_type)
                            st.success("Type added")
                        except ValueError as e:
                            st.warning(str(e))
                    else:
                        st.warning("Name required")
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
                                "Name",
                                name,
                                key=f"edit_name_{name}",
                                on_change=self._update_equipment,
                                args=(name,),
                            )
                            edit_type = st.text_input(
                                "Type",
                                eq_type,
                                key=f"edit_type_{name}",
                                on_change=self._update_equipment,
                                args=(name,),
                            )
                            edit_muscles = st.multiselect(
                                "Muscles",
                                muscles_list,
                                musc_list,
                                key=f"edit_mus_{name}",
                                on_change=self._update_equipment,
                                args=(name,),
                            )
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

            with st.expander("Add Muscle"):
                base_name = st.text_input("Muscle Name", key="base_muscle")
                if st.button("Add Muscle"):
                    if base_name:
                        try:
                            self.muscles_repo.add(base_name)
                            st.success("Muscle added")
                        except ValueError as e:
                            st.warning(str(e))
                    else:
                        st.warning("Name required")

            with st.expander("Muscle Groups", expanded=True):
                groups = self.muscle_groups_repo.fetch_all()
                new_group = st.text_input("New Group", key="new_group")
                if st.button("Add Group"):
                    if new_group:
                        try:
                            self.muscle_groups_repo.add(new_group)
                            st.success("Group added")
                        except ValueError as e:
                            st.warning(str(e))
                    else:
                        st.warning("Name required")
                for g in groups:
                    gexp = st.expander(g)
                    with gexp:
                        new_name = st.text_input("Name", g, key=f"grp_name_{g}")
                        sel = st.multiselect(
                            "Muscles",
                            muscles,
                            self.muscle_groups_repo.fetch_muscles(g),
                            key=f"grp_mus_{g}",
                        )
                        if st.button("Update", key=f"grp_up_{g}"):
                            try:
                                self.muscle_groups_repo.rename(g, new_name)
                                self.muscle_groups_repo.set_members(new_name, sel)
                                st.success("Updated")
                            except ValueError as e:
                                st.warning(str(e))
                        if st.button("Delete", key=f"grp_del_{g}"):
                            try:
                                self.muscle_groups_repo.delete(g)
                                st.success("Deleted")
                            except ValueError as e:
                                st.warning(str(e))

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
            st.header("Exercise Management")
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

        with hr_tab:
            st.header("Heart Rate Logs")
            summary = self.stats.heart_rate_summary()
            with st.expander("Summary", expanded=True):
                metrics = [
                    ("Average", summary["avg"]),
                    ("Min", summary["min"]),
                    ("Max", summary["max"]),
                ]
                self._metric_grid(metrics)
            with st.expander("History", expanded=True):
                rows = self.heart_rates.fetch_range()
                if rows:
                    df = pd.DataFrame(
                        rows,
                        columns=["id", "workout_id", "timestamp", "heart_rate"],
                    )
                    self._responsive_table(
                        df[["timestamp", "heart_rate", "workout_id"]]
                    )
                else:
                    st.write("No logs")

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

            with st.expander("Existing Tags", expanded=False):
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

        with auto_tab:
            st.header("Autoplanner Status")
            last_success = self.autoplan_logs.last_success()
            st.write(f"Last successful run: {last_success or 'never'}")
            errors = self.autoplan_logs.last_errors(5)
            if errors:
                st.write("Recent Errors:")
                for ts, msg in errors:
                    st.write(f"{ts}: {msg}")
            presc_success = self.prescription_logs.last_success()
            st.write(f"Prescription last run: {presc_success or 'never'}")
            presc_errs = self.prescription_logs.last_errors(5)
            if presc_errs:
                st.write("Prescription Errors:")
                for ts, msg in presc_errs:
                    st.write(f"{ts}: {msg}")
            model_map = {
                "performance_model": "rpe",
                "volume_model": "volume",
                "readiness_model": "readiness",
                "progress_model": "progress",
                "rl_goal_model": "goal",
                "injury_model": "injury",
                "adaptation_model": "adaptation",
            }
            badge = (
                lambda flag: f"<span class='badge {'success' if flag else 'error'}'>{'ON' if flag else 'OFF'}</span>"
            )
            for name, prefix in model_map.items():
                train_flag = self.settings_repo.get_bool(
                    f"ml_{prefix}_training_enabled", True
                )
                pred_flag = self.settings_repo.get_bool(
                    f"ml_{prefix}_prediction_enabled", True
                )
                if not train_flag and not pred_flag:
                    continue
                status = self.ml_status.fetch(name)
                st.subheader(name)
                st.markdown(
                    f"Training {badge(train_flag)} Prediction {badge(pred_flag)}",
                    unsafe_allow_html=True,
                )
                load = status['last_loaded'] or 'never'
                train_time = status['last_train'] or 'never'
                pred_time = status['last_predict'] or 'never'
                st.markdown(f"Loaded: <span class='badge warning'>{load}</span>", unsafe_allow_html=True)
                st.markdown(
                    f"Last Train: <span class='badge warning'>{train_time}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"Last Prediction: <span class='badge warning'>{pred_time}</span>",
                    unsafe_allow_html=True,
                )


if __name__ == "__main__":
    import os

    db_path = os.environ.get("DB_PATH", "workout.db")
    yaml_path = os.environ.get("YAML_PATH", "settings.yaml")
    GymApp(db_path=db_path, yaml_path=yaml_path).run()
