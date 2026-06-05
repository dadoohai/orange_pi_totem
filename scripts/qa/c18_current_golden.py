#!/usr/bin/env python3
"""Load the current C18 golden image registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_GOLDEN_PATH = REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "current-golden.json"


def load_current_golden() -> dict[str, Any]:
    data = json.loads(CURRENT_GOLDEN_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "dadooh.c18.current_golden.v1":
        raise RuntimeError("current golden schema mismatch")
    for key in ("image_tag", "image_sha256", "image_version", "image_marker_path", "coldboot_evidence_dir"):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"current golden missing {key}")
    marker_sha = data.get("image_marker_sha256")
    if not isinstance(marker_sha, str) or len(marker_sha) != 64:
        raise RuntimeError("current golden invalid image_marker_sha256")
    return data


if __name__ == "__main__":
    print(json.dumps(load_current_golden(), indent=2, sort_keys=True))
