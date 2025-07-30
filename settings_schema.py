from pydantic import BaseModel, ValidationError

class SettingsSchema(BaseModel):
    theme: str = "light"
    weight_unit: str = "kg"
    time_format: str = "24h"
    timezone: str = "UTC"
    quick_weight_increment: float = 0.5
    rpe_scale: int = 10
    language: str = "en"
    font_size: int = 16
    layout_spacing: float = 1.5
    flex_metric_grid: bool = False
    collapse_header: bool = True
    accent_color: str = "#ff4b4b"

def validate_settings(data: dict) -> None:
    try:
        SettingsSchema(**data)
    except ValidationError as e:
        raise ValueError(str(e))
