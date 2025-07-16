from __future__ import annotations
import io
import torch
from db import MLModelRepository, ExerciseNameRepository
from typing import Iterable

class RPEModel(torch.nn.Module):
    """Simple model storing a single RPE value."""

    def __init__(self, initial: float = 7.0) -> None:
        super().__init__()
        self.value = torch.nn.Parameter(torch.tensor(float(initial)))

    def forward(self) -> torch.Tensor:  # pragma: no cover - simple pass
        return self.value


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
            model = RPEModel()
            opt = torch.optim.SGD(model.parameters(), lr=self.lr)
            if blob is not None:
                buffer = io.BytesIO(blob)
                state = torch.load(buffer)
                model.load_state_dict(state)
            self.models[canonical] = (model, opt)
        return self.models[canonical]

    def train(self, name: str, rpe: float) -> None:
        model, opt = self._get(name)
        opt.zero_grad()
        pred = model().view(1)
        target = torch.tensor([rpe], dtype=torch.float32)
        loss = torch.nn.functional.mse_loss(pred, target)
        loss.backward()
        opt.step()
        buf = io.BytesIO()
        torch.save(model.state_dict(), buf)
        self.repo.save(self.names.canonical(name), buf.getvalue())

    def predict(self, name: str) -> float:
        model, _ = self._get(name)
        with torch.no_grad():
            return float(model().item())


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
