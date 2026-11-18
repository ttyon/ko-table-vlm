"""manifest(jsonl) 읽기/쓰기 공용 함수."""
from __future__ import annotations

import json
from pathlib import Path


def load_manifest(path: str | Path) -> list[dict]:
    """각 레코드의 image 를 절대경로(image_path)로 풀어서 돌려준다."""
    path = Path(path)
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["image_path"] = str((path.parent / r["image"]).resolve())
                rows.append(r)
    return rows


def load_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def append_jsonl(path: str | Path, rec: dict):
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
