from __future__ import annotations
import json, os, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import urllib.request

@dataclass
class Game:
    source: str
    app_id: str
    name: str
    launch_uri: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.app_id}"

_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')

def _unescape(s: str) -> str:
    return (s.replace("\\\\", "\\").replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t"))

def _parse_vdf(text: str) -> dict:
    tokens = _TOKEN_RE.findall(text)
    pos = 0
    def parse_block() -> dict:
        nonlocal pos
        out: dict = {}
        while pos < len(tokens):
            s, br = tokens[pos]
            if br == "}":
                pos += 1
                return out
            if br == "{":
                pos += 1
                continue
            key = _unescape(s)
            pos += 1
            if pos >= len(tokens): break
            s2, br2 = tokens[pos]
            if br2 == "{":
                pos += 1
                out[key] = parse_block()
            else:
                out[key] = _unescape(s2)
                pos += 1
        return out
    return parse_block()

_STEAM_JUNK_IDS = {228980, 1070560, 1391110, 1628350, 1493710, 961940, 1887720, 2348590, 1580130}
_STEAM_JUNK_PREFIX = ("Proton ", "Steam Linux Runtime", "Steamworks Common")

def _is_steam_junk(app_id: str, name: str) -> bool:
    try:
        if int(app_id) in _STEAM_JUNK_IDS: return True
    except ValueError: pass
    return any(name.startswith(p) for p in _STEAM_JUNK_PREFIX)

def _steam_root() -> Optional[Path]:
    if sys.platform == "win32":
        try:
            import winreg
            for hive, sub, name in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"), (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        p, _ = winreg.QueryValueEx(k, name)
                        if p and Path(p).exists(): return Path(p)
                except OSError: continue
        except ImportError: pass
        return None
    if sys.platform == "darwin":
        p = Path.home() / "Library/Application Support/Steam"
        return p if p.exists() else None
    for p in (Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"):
        if p.exists(): return p
    return None

def _steam_libraries(root: Path) -> list[Path]:
    libs = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        try:
            data = _parse_vdf(vdf.read_text(encoding="utf-8", errors="ignore"))
            for v in data.get("libraryfolders", {}).values():
                if isinstance(v, dict) and "path" in v:
                    p = Path(v["path"])
                    if p.exists(): libs.append(p)
        except Exception: pass
    seen, out = set(), []
    for p in libs:
        try: rp = p.resolve()
        except OSError: rp = p
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out

def scan_steam() -> list[Game]:
    root = _steam_root()
    if not root: return []
    games: list[Game] = []
    for lib in _steam_libraries(root):
        steamapps = lib / "steamapps"
        if not steamapps.exists(): continue
        for acf in steamapps.glob("appmanifest_*.acf"):
            try:
                data = _parse_vdf(acf.read_text(encoding="utf-8", errors="ignore"))
                st = data.get("AppState", {})
                app_id, name = st.get("appid"), st.get("name")
                if not app_id or not name or _is_steam_junk(str(app_id), name): continue
                games.append(Game(source="steam", app_id=str(app_id), name=name, launch_uri=f"steam://rungameid/{app_id}"))
            except Exception: continue
    return games

def scan_epic() -> list[Game]:
    games: list[Game] = []
    manifest_dir = None
    if sys.platform == "win32":
        pd = os.environ.get("ProgramData", r"C:\ProgramData")
        manifest_dir = Path(pd) / "Epic/EpicGamesLauncher/Data/Manifests"
    elif sys.platform == "darwin":
        manifest_dir = Path("/Users/Shared/Epic Games/EpicGamesLauncher/Data/Manifests")

    if not manifest_dir or not manifest_dir.exists(): return games

    for f in manifest_dir.glob("*.item"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            app_name = data.get("AppName") or data.get("MainGameAppName")
            if not app_name: continue
            games.append(Game(
                source="epic", app_id=app_name, name=data.get("DisplayName") or app_name,
                launch_uri=f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true"
            ))
        except Exception: continue
    return games

def scan_all() -> list[Game]:
    games = scan_steam() + scan_epic()
    seen, out = set(), []
    for g in games:
        if g.key in seen: continue
        seen.add(g.key)
        out.append(g)
    out.sort(key=lambda g: g.name.lower())
    return out

def get_steam_cover_url(app_id: str) -> str:
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"

def fetch_steam_details(app_id: str) -> dict:
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=russian"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        entry = data.get(app_id)
        if entry and entry.get("success"):
            d = entry["data"]
            return {
                "description": d.get("short_description", ""),
                "genres": [g["description"] for g in d.get("genres", [])],
            }
    except Exception:
        pass
    return {}
