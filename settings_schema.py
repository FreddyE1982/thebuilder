from pydantic import BaseModel, ValidationError

class SettingsSchema(BaseModel):
    theme: str = "light"
    weight_unit: str = "kg"
    time_format: str = "24h"

def validate_settings(data: dict) -> None:
    try:
        SettingsSchema(**data)
    except ValidationError as e:
        raise ValueError(str(e))
