from typing import Any, Optional
import imgkit


class ScreengrabberService:
    def __init__(self):
        pass

    def get_screenshot(self, url: str, options: Optional[dict[str, Any]] = {}) -> bytes:
        return imgkit.from_url(
            url=url,
            options=options,
            output_path=None,
        )
