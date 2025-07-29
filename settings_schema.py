from pydantic import BaseModel, ValidationError

class SettingsSchema(BaseModel):
    theme: str = "light"
    weight_unit: str = "kg"
    time_format: str = "24h"
    rpe_scale: int = 10
    language: str = "en"
    collapse_header: bool = True

def validate_settings(data: dict) -> None:
    try:
        SettingsSchema(**data)
    except ValidationError as e:
        raise ValueError(str(e))
