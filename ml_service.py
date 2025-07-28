from __future__ import annotations
import io
import torch
from db import (
    MLModelRepository,
    ExerciseNameRepository,
    MLLogRepository,
    MLModelStatusRepository,
)
from typing import Iterable, Optional

torch.manual_seed(0)


class RPEModel(torch.nn.Module):
    """Feed-forward network predicting RPE with confidence."""

    def __init__(self, input_size: int = 3, hidden_size: int = 16) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, hidden_size),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_size, 1),
        )
        self.log_var = torch.nn.Parameter(torch.zeros(1))

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:  # pragma: no cover - trivial
        pred = self.net(x)
        var = torch.exp(self.log_var)
        conf = 1.0 / (var + 1e-6)
        return pred, conf


class BaseModelService:
    """Base functionality for persistent Torch models."""

    def __init__(
        self,
        repo: MLModelRepository,
        name: str,
        lr: float,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        self.repo = repo
        self.name = name
        self.lr = lr
        self.status_repo = status_repo

    def _save_state(
        self,
        model: torch.nn.Module,
        opt: torch.optim.Optimizer,
        extra: Optional[dict] = None,
    ) -> None:
        buf = io.BytesIO()
        state = {"model": model.state_dict(), "opt": opt.state_dict()}
        if extra:
            state.update(extra)
        torch.save(state, buf)
        self.repo.save(self.name, buf.getvalue())
        if self.status_repo is not None:
            self.status_repo.set_trained(self.name)

    def _load_state(self) -> Optional[dict]:
        blob = self.repo.load(self.name)
        if self.status_repo is not None:
            self.status_repo.set_loaded(self.name)
        if blob is None:
            return None
        buffer = io.BytesIO(blob)
        state = torch.load(buffer)
        return state


class PerformanceModelService:
    """Handle online training and prediction of RPE values."""

    def __init__(
        self,
        repo: MLModelRepository,
        name_repo: ExerciseNameRepository,
        log_repo: MLLogRepository | None = None,
        status_repo: MLModelStatusRepository | None = None,
        lr: float = 0.1,
        raw_repo: MLTrainingRawRepository | None = None,
    ) -> None:
        self.repo = repo
        self.names = name_repo
        self.log_repo = log_repo
        self.status_repo = status_repo
        self.lr = lr
        self.raw_repo = raw_repo
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
            if self.status_repo is not None:
                self.status_repo.set_loaded("performance_model")
            self.models[canonical] = (model, opt)
        return self.models[canonical]

    def train(
        self, name: str, reps: int, weight: float, rpe: float, prev_rpe: float
    ) -> None:
        model, opt = self._get(name)
        opt.zero_grad()
        x = torch.tensor(
            [[weight / 1000.0, reps / 10.0, prev_rpe / 10.0]], dtype=torch.float32
        )
        pred, _ = model(x)
        target = torch.tensor([rpe / 10.0], dtype=torch.float32)
        var = torch.exp(model.log_var)
        loss = 0.5 * ((pred - target) ** 2 / var + torch.log(var))
        loss.backward()
        opt.step()
        if self.raw_repo is not None:
            vec = f"{weight}|{reps}|{prev_rpe}"
            self.raw_repo.add("performance_model", vec, rpe)
        buf = io.BytesIO()
        torch.save(model.state_dict(), buf)
        self.repo.save(self.names.canonical(name), buf.getvalue())
        if self.status_repo is not None:
            self.status_repo.set_trained("performance_model")

    def predict(
        self, name: str, reps: int, weight: float, prev_rpe: float
    ) -> tuple[float, float]:
        model, _ = self._get(name)
        with torch.no_grad():
            x = torch.tensor(
                [[weight / 1000.0, reps / 10.0, prev_rpe / 10.0]], dtype=torch.float32
            )
            pred, conf = model(x)
            value = float(pred.item() * 10.0)
            conf_v = float(conf.item())
        if self.log_repo is not None:
            self.log_repo.add(self.names.canonical(name), value, conf_v)
        if self.status_repo is not None:
            self.status_repo.set_prediction("performance_model")
        return value, conf_v

    def cross_validate(self, folds: int = 5) -> float:
        if self.raw_repo is None:
            return 0.0
        data = self.raw_repo.fetch("performance_model")
        if len(data) < folds or folds < 2:
            return 0.0
        fold_size = len(data) // folds
        errors: list[float] = []
        for i in range(folds):
            test = data[i * fold_size : (i + 1) * fold_size]
            train = data[: i * fold_size] + data[(i + 1) * fold_size :]
            model = RPEModel()
            opt = torch.optim.SGD(model.parameters(), lr=self.lr)
            for inp, tgt in train:
                x = torch.tensor([inp], dtype=torch.float32)
                y = torch.tensor([tgt / 10.0], dtype=torch.float32)
                pred, _ = model(x)
                var = torch.exp(model.log_var)
                loss = 0.5 * ((pred - y) ** 2 / var + torch.log(var))
                loss.backward()
                opt.step()
                opt.zero_grad()
            mse = 0.0
            for inp, tgt in test:
                with torch.no_grad():
                    x = torch.tensor([inp], dtype=torch.float32)
                    pred, _ = model(x)
                    mse += float((pred.item() - tgt / 10.0) ** 2)
            errors.append(mse / len(test))
        return sum(errors) / len(errors)


class VolumePredictor(torch.nn.Module):
    """Simple linear model for forecasting volume."""

    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(3, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.linear(x)


class VolumeModelService(BaseModelService):
    """Handle online training and prediction of daily volumes."""

    SCALE: float = 1000.0

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.001,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "volume_model", lr, status_repo)
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[VolumePredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = VolumePredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        state = self._load_state()
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        self._save_state(self.model, self.opt)
        self.initialized = True

    def train(self, features: Iterable[float], target: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor([f / self.SCALE for f in features], dtype=torch.float32).view(
            1, -1
        )
        y = torch.tensor([target / self.SCALE], dtype=torch.float32)
        pred = self.model(x).view(1)
        loss = torch.nn.functional.mse_loss(pred, y)
        loss.backward()
        self.opt.step()
        self._save()

    def predict(
        self, features: Iterable[float], fallback: float | None = None
    ) -> float:
        if not self.initialized and fallback is not None:
            return float(fallback)
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor(
                [f / self.SCALE for f in features], dtype=torch.float32
            ).view(1, -1)
            pred = self.model(x)
            val = float(pred.item() * self.SCALE)
        if self.status_repo is not None:
            self.status_repo.set_prediction("volume_model")
        return val


class ReadinessPredictor(torch.nn.Module):
    """Simple linear model for readiness estimation."""

    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.linear(x)


class ReadinessModelService(BaseModelService):
    """Handle online training and prediction of readiness values."""

    SCALE: float = 10.0

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.01,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "readiness_model", lr, status_repo)
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[ReadinessPredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = ReadinessPredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        state = self._load_state()
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        self._save_state(self.model, self.opt)
        self.initialized = True

    def train(self, stress: float, fatigue: float, readiness: float) -> None:
        self.model.train()
        self.opt.zero_grad()
        x = torch.tensor(
            [[stress / self.SCALE, fatigue / self.SCALE]], dtype=torch.float32
        )
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
            x = torch.tensor(
                [[stress / self.SCALE, fatigue / self.SCALE]], dtype=torch.float32
            )
            pred = self.model(x)
            val = float(pred.item() * self.SCALE)
        if self.status_repo is not None:
            self.status_repo.set_prediction("readiness_model")
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


class ProgressModelService(BaseModelService):
    """Handle online training and prediction of 1RM values using an LSTM."""

    SCALE: float = 200.0

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.001,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "progress_model", lr, status_repo)
        self.model, self.opt, self.initialized, self.history = self._load()

    def _load(self) -> tuple[LSTMProgressPredictor, torch.optim.Optimizer, bool, list]:
        torch.manual_seed(0)
        model = LSTMProgressPredictor()
        opt = torch.optim.SGD(model.parameters(), lr=self.lr)
        state = self._load_state()
        history: list = []
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            history = state.get("history", [])
            return model, opt, True, history
        return model, opt, False, history

    def _save(self) -> None:
        self._save_state(
            self.model,
            self.opt,
            extra={"history": self.history},
        )
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
            val = float(pred.item() * self.SCALE)
        if self.status_repo is not None:
            self.status_repo.set_prediction("progress_model")
        return val


class RLGoalNet(torch.nn.Module):
    """Simple DQN for adaptive goal setting."""

    def __init__(
        self, input_size: int = 3, hidden_size: int = 16, actions: int = 3
    ) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_size, hidden_size),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_size, actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - trivial
        return self.net(x)


class RLGoalModelService(BaseModelService):
    """Deep Q-learning model for dynamic exercise goals."""

    ACTIONS = [-2.5, 0.0, 2.5]

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.001,
        gamma: float = 0.9,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "rl_goal_model", lr, status_repo)
        self.gamma = gamma
        self.model, self.opt, self.initialized, self.history = self._load()
        self.pending: dict[int, tuple[list[float], int]] = {}

    def _load(self) -> tuple[RLGoalNet, torch.optim.Optimizer, bool, list]:
        torch.manual_seed(0)
        model = RLGoalNet()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        state = self._load_state()
        history: list = []
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            history = state.get("history", [])
            return model, opt, True, history
        return model, opt, False, history

    def _save(self) -> None:
        self._save_state(
            self.model,
            self.opt,
            extra={"history": self.history},
        )
        self.initialized = True

    def predict(self, state: Iterable[float]) -> int:
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor(list(state), dtype=torch.float32)
            q = self.model(x)
            action = int(torch.argmax(q).item())
        if self.status_repo is not None:
            self.status_repo.set_prediction("rl_goal_model")
        return action

    def train_step(
        self,
        state: Iterable[float],
        action: int,
        reward: float,
        next_state: Iterable[float],
    ) -> None:
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


class InjuryRiskModelService(BaseModelService):
    """Predict injury probability based on training load metrics."""

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.001,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "injury_model", lr, status_repo)
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[InjuryRiskPredictor, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = InjuryRiskPredictor()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        state = self._load_state()
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        self._save_state(self.model, self.opt)
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
            val = float(pred.item())
        if self.status_repo is not None:
            self.status_repo.set_prediction("injury_model")
        return val


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


class AdaptationModelService(BaseModelService):
    """Predict overall adaptation index from multiple metrics."""

    def __init__(
        self,
        repo: MLModelRepository,
        lr: float = 0.001,
        status_repo: MLModelStatusRepository | None = None,
    ) -> None:
        super().__init__(repo, "adaptation_model", lr, status_repo)
        self.model, self.opt, self.initialized = self._load()

    def _load(self) -> tuple[FusionNet, torch.optim.Optimizer, bool]:
        torch.manual_seed(0)
        model = FusionNet()
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        state = self._load_state()
        if state is not None:
            model.load_state_dict(state.get("model", {}))
            opt.load_state_dict(state.get("opt", {}))
            return model, opt, True
        return model, opt, False

    def _save(self) -> None:
        self._save_state(self.model, self.opt)
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
        if self.status_repo is not None:
            self.status_repo.set_prediction("adaptation_model")
        return (val + fallback) / 2
