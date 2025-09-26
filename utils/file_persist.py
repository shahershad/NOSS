# utils/file_persist.py
# Simple, robust JSON persistence for IR/GT custom keywords.
# Writes to ".persist/ir_keywords.json" and ".persist/gt_keywords.json" by default.
# Set env KW_STORE_DIR to change the directory.

from typing import Dict, Any
import os, json, tempfile

BASE_DIR = os.environ.get("KW_STORE_DIR", ".persist")

def _path(prefix: str) -> str:
    fname = "ir_keywords.json" if prefix == "ir" else (
        "gt_keywords.json" if prefix == "gt" else f"{prefix}_keywords.json"
    )
    return os.path.join(BASE_DIR, fname)

def load(prefix: str) -> Dict[str, Any]:
    p = _path(prefix)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        # Keep UI usable even if file is malformed
        return {}

def save(prefix: str, data: Dict[str, Any]) -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    p = _path(prefix)
    fd, tmp = tempfile.mkstemp(dir=BASE_DIR, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Atomic replace
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise

def clear(prefix: str) -> None:
    p = _path(prefix)
    try:
        os.remove(p)
    except FileNotFoundError:
        pass
