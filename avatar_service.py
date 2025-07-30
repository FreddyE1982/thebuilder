from __future__ import annotations
import io
from PIL import Image, ImageDraw
from db import SettingsRepository


class AvatarService:
    """Manage default avatars stored in the database."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._repo = settings_repo
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        for idx, color in [(1, "#888888"), (2, "#aaaaaa")]:
            key = f"default_avatar{idx}"
            if not self._repo.get_text(key, ""):
                self._repo.set_bytes(key, self._generate_avatar(color))

    def _generate_avatar(self, color: str) -> bytes:
        img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), fill=color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def get_default(self, idx: int) -> bytes:
        key = f"default_avatar{idx}"
        data = self._repo.get_bytes(key)
        if data is None:
            color = "#888888" if idx == 1 else "#aaaaaa"
            data = self._generate_avatar(color)
            self._repo.set_bytes(key, data)
        return data
