from __future__ import annotations
import io
import torch
from db import MLModelRepository, ExerciseNameRepository
from typing import Iterable

torch.manual_seed(0)

class RPEModel(torch.nn.Module):
    """Feed-forward network predicting RPE from basic set features."""

    def __init__(self, input_size: int = 3, hidden_size: int = 16) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, hidden_size),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_size, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.net(x)


class PerformanceModelService:
    """Handle online training and prediction of RPE values."""

    def __init__(
        self,
        repo: MLModelRepository,
        name_repo: ExerciseNameRepository,
        lr: float = 0.1,
    ) -> None:
        self.repo = repo
        self.names = name_repo
        self.lr = lr
        self.models: dict[str, tuple[RPEModel, torch.optim.Optimizer]] = {}

    def _get(self, name: str) -> tuple[RPEModel, torch.optim.Optimizer]:
        canonical = self.names.canonical(name)
        if canonical not in self.models:
            blob = self.repo.load(canonical)
            torch.manual_seed(0)
            model = RPEModel()
            opt = torch.optim.SGD(model.parameters(), lr=self.lr)
            if blob is not None:
                buffer = io.BytesIO(blob)
                state = torch.load(buffer)
                model.load_state_dict(state)
            self.models[canonical] = (model, opt)
        return self.models[canonical]

    def train(self, name: str, reps: int, weight: float, rpe: float) -> None:
        model, opt = self._get(name)
        opt.zero_grad()
        x = torch.tensor([[weight / 1000.0, reps / 10.0, rpe / 10.0]], dtype=torch.float32)
        pred = model(x).view(1)
        target = torch.tensor([rpe / 10.0], dtype=torch.float32)
        loss = torch.nn.functional.mse_loss(pred, target)
        loss.backward()
        opt.step()
        buf = io.BytesIO()
        torch.save(model.state_dict(), buf)
        self.repo.save(self.names.canonical(name), buf.getvalue())

    def predict(self, name: str, reps: int, weight: float, prev_rpe: float) -> float:
        model, _ = self._get(name)
        with torch.no_grad():
            x = torch.tensor([[weight / 1000.0, reps / 10.0, prev_rpe / 10.0]], dtype=torch.float32)
            val = model(x)
            return float(val.item() * 10.0)


class VolumePredictor(torch.nn.Module):
    """Simple linear model for forecasting volume."""

    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(3, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.linear(x)


class VolumeModelService:
    """Handle online training and prediction of daily volumes."""

    SCALE: float = 1000.0

    def __init__(self, repo: MLModelRepository, lr: float = 0.001) -> None:
        self.repo = repo
        self.lr = lr
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[VolumePredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = VolumePredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        blob = self.repo.load("volume_model")
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save({"model": self.model.state_dict(), "opt": self.opt.state_dict()}, buf)
        self.repo.save("volume_model", buf.getvalue())
        self.initialized = True

    def train(self, features: Iterable[float], target: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([f / self.SCALE for f in features], dtype=torch.float32).view(1, -1)
        y = torch.tensor([target / self.SCALE], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.mse_loss(pred, y)
        loss.backward()
        self.opt.step()
        self._save()

    def predict(self, features: Iterable[float], fallback: float | None = None) -> float:
        if not self.initialized and fallback is not None:
            return float(fallback)
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor([f / self.SCALE for f in features], dtype=torch.float32).view(1, -1)
            pred = self.model(x)
            return float(pred.item() * self.SCALE)


class ReadinessPredictor(torch.nn.Module):
    """Simple linear model for readiness estimation."""

    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.linear(x)


class ReadinessModelService:
    """Handle online training and prediction of readiness values."""

    SCALE: float = 10.0

    def __init__(self, repo: MLModelRepository, lr: float = 0.01) -> None:
        self.repo = repo
        self.lr = lr
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[ReadinessPredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = ReadinessPredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        blob = self.repo.load("readiness_model")
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save({"model": self.model.state_dict(), "opt": self.opt.state_dict()}, buf)
        self.repo.save("readiness_model", buf.getvalue())
        self.initialized = True

    def train(self, stress: float, fatigue: float, readiness: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([[stress / self.SCALE, fatigue / self.SCALE]], dtype=torch.float32)
        y = torch.tensor([readiness / self.SCALE], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.mse_loss(pred, y)
        loss.backward()
        self.opt.step()
        self._save()

    def predict(self, stress: float, fatigue: float, fallback: float) -> float:
        if not self.initialized:
            return fallback
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor([[stress / self.SCALE, fatigue / self.SCALE]], dtype=torch.float32)
            pred = self.model(x)
            val = float(pred.item() * self.SCALE)
        return (val + fallback) / 2


class LSTMProgressPredictor(torch.nn.Module):
    """LSTM based model for estimating 1RM progression over time."""

    def __init__(self, input_size: int = 2, hidden_size: int = 16) -> None:
        super().__init__()
        self.lstm = torch.nn.LSTM(input_size, hidden_size, batch_first=True)
        self.linear = torch.nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.linear(out)


class ProgressModelService:
    """Handle online training and prediction of 1RM values using an LSTM."""

    SCALE: float = 200.0

    def __init__(self, repo: MLModelRepository, lr: float = 0.001) -> None:
        self.repo = repo
        self.lr = lr
        self.model, self.opt, self.initialized, self.history = self._load()

    def _load(self) -> tuple[LSTMProgressPredictor, torch.optim.Optimizer, bool, list]:
        torch.manual_seed(0)
        model = LSTMProgressPredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        blob = self.repo.load("progress_model")
        history: list = []
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            history = state.get("history", [])
            return model, opt, True, history
        return model, opt, False, history

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save(
            {"model": self.model.state_dict(), "opt": self.opt.state_dict(), "history": self.history},
            buf,
        )
        self.repo.save("progress_model", buf.getvalue())
        self.initialized = True

    def train(self, time_index: float, one_rm: float, feature: float = 0.0) -> None:
        if not self.history:
            self.history.append([time_index / 100.0, feature])
            return
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([self.history], dtype=torch.float32)
        y = torch.tensor([one_rm / self.SCALE], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.mse_loss(pred, y)
        loss.backward()
        self.opt.step()
        self.history.append([time_index / 100.0, feature])
        self._save()

    def predict(self, time_index: float, feature: float = 0.0) -> float:
        if not self.initialized and not self.history:
            return 0.0
        self.model.eval()
        seq = self.history + [[time_index / 100.0, feature]]
        with torch.no_grad():
            x = torch.tensor([seq], dtype=torch.float32)
            pred = self.model(x)
            return float(pred.item() * self.SCALE)


class RLGoalNet(torch.nn.Module):
    """Simple DQN for adaptive goal setting."""

    def __init__(self, input_size: int = 3, hidden_size: int = 16, actions: int = 3) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, hidden_size),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_size, actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.net(x)


class RLGoalModelService:
    """Deep Q-learning model for dynamic exercise goals."""

    ACTIONS = [-2.5, 0.0, 2.5]

    def __init__(self, repo: MLModelRepository, lr: float = 0.001, gamma: float = 0.9) -> None:
        self.repo = repo
        self.lr = lr
        self.gamma = gamma
        self.model, self.opt, self.initialized, self.history = self._load()
        self.pending: dict[int, tuple[list[float], int]] = {}

    def _load(self) -> tuple[RLGoalNet, torch.optim.Optimizer, bool, list]:
        torch.manual_seed(0)
        model = RLGoalNet()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        blob = self.repo.load("rl_goal_model")
        history: list = []
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            history = state.get("history", [])
            return model, opt, True, history
        return model, opt, False, history

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save(
            {"model": self.model.state_dict(), "opt": self.opt.state_dict(), "history": self.history},
            buf,
        )
        self.repo.save("rl_goal_model", buf.getvalue())
        self.initialized = True

    def predict(self, state: Iterable[float]) -> int:
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor(list(state), dtype=torch.float32)
            q = self.model(x)
            return int(torch.argmax(q).item())

    def train_step(self, state: Iterable[float], action: int, reward: float, next_state: Iterable[float]) -> None:
        self.model.train()
        self.opt.zero_grad()
        s = torch.tensor(list(state), dtype=torch.float32)
        ns = torch.tensor(list(next_state), dtype=torch.float32)
        q = self.model(s)[action]
        with torch.no_grad():
            next_q = torch.max(self.model(ns))
        target = reward + self.gamma * next_q
        loss = torch.nn.functional.mse_loss(q, target)
        loss.backward()
        self.opt.step()
        self._save()

    def register(self, set_id: int, state: list[float], action: int) -> None:
        self.pending[set_id] = (state, action)

    def complete(self, set_id: int, new_state: list[float], reward: float) -> None:
        if set_id in self.pending:
            state, action = self.pending.pop(set_id)
            self.train_step(state, action, reward, new_state)


class InjuryRiskPredictor(torch.nn.Module):
    """Feed-forward network for injury risk estimation."""

    def __init__(self, input_size: int = 3) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, 8),
            torch.nn.ReLU(),
            torch.nn.Linear(8, 1),
            torch.nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.net(x)


class InjuryRiskModelService:
    """Predict injury probability based on training load metrics."""

    def __init__(self, repo: MLModelRepository, lr: float = 0.001) -> None:
        self.repo = repo
        self.lr = lr
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[InjuryRiskPredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = InjuryRiskPredictor()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        blob = self.repo.load("injury_model")
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save({"model": self.model.state_dict(), "opt": self.opt.state_dict()}, buf)
        self.repo.save("injury_model", buf.getvalue())
        self.initialized = True

    def train(self, features: Iterable[float], label: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([list(features)], dtype=torch.float32)
        y = torch.tensor([label], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.binary_cross_entropy(pred, y)
        loss.backward()
        self.opt.step()
        self._save()

    def predict(self, features: Iterable[float]) -> float:
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor([list(features)], dtype=torch.float32)
            pred = self.model(x)
            return float(pred.item())


class FusionNet(torch.nn.Module):
    """Multi-modal network for overall adaptation scoring."""

    def __init__(self, input_size: int = 5, hidden_size: int = 16) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, hidden_size),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_size, 1),
            torch.nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.net(x)


class AdaptationModelService:
    """Predict overall adaptation index from multiple metrics."""

    def __init__(self, repo: MLModelRepository, lr: float = 0.001) -> None:
        self.repo = repo
        self.lr = lr
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[FusionNet, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = FusionNet()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        blob = self.repo.load("adaptation_model")
        if blob is not None:
            buffer = io.BytesIO(blob)
            state = torch.load(buffer)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["opt"])
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        buf = io.BytesIO()
        torch.save({"model": self.model.state_dict(), "opt": self.opt.state_dict()}, buf)
        self.repo.save("adaptation_model", buf.getvalue())
        self.initialized = True

    def train(self, features: Iterable[float], label: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([list(features)], dtype=torch.float32)
        y = torch.tensor([label], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.mse_loss(pred, y)
        loss.backward()
        self.opt.step()
        self._save()

    def predict(self, features: Iterable[float], fallback: float) -> float:
        if not self.initialized:
            return fallback
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor([list(features)], dtype=torch.float32)
            pred = self.model(x)
            val = float(pred.item())
        return (val + fallback) / 2
