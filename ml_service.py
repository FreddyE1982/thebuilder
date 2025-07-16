import io
import torch
from db import MLModelRepository, ExerciseNameRepository

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
        pred = model()
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
