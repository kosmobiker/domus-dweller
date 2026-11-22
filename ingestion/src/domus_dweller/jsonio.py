from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Write JSON to `path` via a temp file + rename.

    The enrich step rewrites its own input file in place (`--input` and `--output`
    point at the same path in the daily Makefile target). A plain `write_text`
    truncates the file first, so a timeout or crash mid-write leaves a corrupt
    artifact that the downstream sink cannot load. `os.replace` is atomic on the
    same filesystem, so readers either see the old file or the new one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
