from __future__ import annotations
import json, urllib.request
from pathlib import Path
from typing import Optional

DATA_DIR = Path.home() / ".coop_launcher"
CACHE_FILE = DATA_DIR / "coop_cache.json"
FAV_FILE = DATA_DIR / "favorites.json"

COOP_CATS = {9, 38, 39}


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_cache() -> dict[str, bool]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict[str, bool]) -> None:
    _ensure_dir()
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_coop_info(app_id: str) -> Optional[bool]:
    url = (
        "https://store.steampowered.com/api/appdetails"
        f"?appids={app_id}&filters=categories&l=english"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "coop-launcher/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    entry = data.get(app_id)
    if not entry or not entry.get("success"):
        return None
    cats = {c["id"] for c in entry["data"].get("categories", [])}
    return bool(cats & COOP_CATS)


def load_favorites() -> list[str]:
    if not FAV_FILE.exists():
        return []
    try:
        return json.loads(FAV_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_favorites(favs) -> None:
    _ensure_dir()
    FAV_FILE.write_text(
        json.dumps(sorted(favs), ensure_ascii=False, indent=2), encoding="utf-8"
    )
