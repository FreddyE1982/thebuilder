class EnvironmentDetector:
    """Detects runtime environment features."""

    @staticmethod
    def is_pythonista() -> bool:
        """Return True if running inside Pythonista."""
        try:
            import ui  # type: ignore
            _ = ui.View  # access attribute to ensure module works
            return True
        except Exception:
            return False


class RestClient:
    """Minimal REST client using urllib for Pythonista."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        import json
        from urllib import request, parse

        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if params:
            encoded = parse.urlencode(params).encode()
            if method.upper() == "GET":
                url = f"{url}?{encoded.decode()}"
            else:
                data = encoded
        req = request.Request(url, data=data, method=method.upper(), headers=headers)
        with request.urlopen(req) as resp:
            body = resp.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"text": body}

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params)

    def post(self, path: str, params: dict | None = None) -> dict:
        return self._request("POST", path, params)

    def put(self, path: str, params: dict | None = None) -> dict:
        return self._request("PUT", path, params)

    def delete(self, path: str, params: dict | None = None) -> dict:
        return self._request("DELETE", path, params)


class PythonistaApp:
    """Basic Pythonista GUI using ui module."""

    def __init__(self, api_url: str = "http://localhost:8000") -> None:
        import ui

        self.client = RestClient(api_url)
        self.view = ui.View(name="Workout Logger")
        self.view.background_color = "white"
        self.tabs = ui.SegmentedControl(items=[
            "Log",
            "Plan",
            "Library",
            "History",
            "Statistics",
            "Settings",
        ])
        self.tabs.frame = (0, 0, self.view.width, 32)
        self.tabs.flex = "W"
        self.tabs.action = self._tab_changed
        self.view.add_subview(self.tabs)
        self.content = ui.View(frame=(0, 32, self.view.width, self.view.height - 32))
        self.content.flex = "WH"
        self.view.add_subview(self.content)
        self._tab_changed(self.tabs)

    def _tab_changed(self, sender) -> None:  # noqa: D401
        """Handle tab switch."""
        for sub in list(self.content.subviews):
            sub.remove_from_superview()
        idx = sender.selected_index
        if idx == 0:
            self._log_tab()
        elif idx == 1:
            self._plan_tab()
        elif idx == 2:
            self._library_tab()
        elif idx == 3:
            self._history_tab()
        elif idx == 4:
            self._stats_tab()
        else:
            self._settings_tab()

    def _log_tab(self) -> None:
        import ui

        view = ui.View(frame=self.content.bounds, flex="WH")
        btn = ui.Button(title="New Workout")
        btn.frame = (10, 10, 120, 32)
        btn.action = self._create_workout
        view.add_subview(btn)
        self.content.add_subview(view)

    def _create_workout(self, sender) -> None:
        res = self.client.post("/workouts")
        import ui

        ui.alert("Workout", f"Created {res.get('id')}")

    def _plan_tab(self) -> None:
        view = self._not_implemented_view()
        self.content.add_subview(view)

    def _library_tab(self) -> None:
        view = self._not_implemented_view()
        self.content.add_subview(view)

    def _history_tab(self) -> None:
        view = self._not_implemented_view()
        self.content.add_subview(view)

    def _stats_tab(self) -> None:
        view = self._not_implemented_view()
        self.content.add_subview(view)

    def _settings_tab(self) -> None:
        view = self._not_implemented_view()
        self.content.add_subview(view)

    def _not_implemented_view(self):
        import ui

        v = ui.View(frame=self.content.bounds, flex="WH")
        lbl = ui.Label(text="Feature not yet implemented")
        lbl.center = v.center
        lbl.flex = "LRTB"
        v.add_subview(lbl)
        return v

    def run(self) -> None:
        import ui

        self.view.present(style="fullscreen")
        ui.run()
