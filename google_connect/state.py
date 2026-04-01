from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.state_dir / f"{name}.json"

    def load(self, name: str, default: Any | None = None) -> Any:
        path = self.path_for(name)
        if not path.exists():
            return default
        return json.loads(path.read_text())

    def save(self, name: str, value: Any) -> None:
        path = self.path_for(name)
        path.write_text(json.dumps(value, indent=2, sort_keys=True))
