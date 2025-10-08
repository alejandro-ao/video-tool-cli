from __future__ import annotations

import sys
from typing import Any

MODULE_NAME = "video_tool.video_processor"


class ModuleAttrProxy:
    """Proxy that always resolves attributes against the package module."""

    def __init__(self, attr_name: str):
        self._attr_name = attr_name

    def _target(self) -> Any:
        module = sys.modules.get(MODULE_NAME)
        if module is None:
            raise RuntimeError(
                f"Module '{MODULE_NAME}' is not loaded; cannot resolve '{self._attr_name}'"
            )
        return getattr(module, self._attr_name)

    def __getattribute__(self, item: str) -> Any:
        if item == "__call__":
            try:
                target = object.__getattribute__(self, "_target")()
            except RuntimeError:
                raise AttributeError(item)
            if not hasattr(target, "__call__"):
                raise AttributeError(item)
        return object.__getattribute__(self, item)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._target(), item)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._target()(*args, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<ModuleAttrProxy for {MODULE_NAME}.{self._attr_name}>"


logger = ModuleAttrProxy("logger")
VideoFileClip = ModuleAttrProxy("VideoFileClip")
AudioSegment = ModuleAttrProxy("AudioSegment")
detect_nonsilent = ModuleAttrProxy("detect_nonsilent")
OpenAI = ModuleAttrProxy("OpenAI")
Groq = ModuleAttrProxy("Groq")
