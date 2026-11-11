import json
import urllib.request

# ⚠️ ВСТАВЬ СВОИ ДАННЫЕ СЮДА:
STEAM_API_KEY = "ВСТАВЬ_СВОЙ_КЛЮЧ"
STEAM_ID = "s_tima7"


def fetch_steam_friends() -> list:
    if not STEAM_API_KEY or STEAM_API_KEY == "ВСТАВЬ_СВОЙ_КЛЮЧ":
        return []
    
    url = f"https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&relationship=friend"
    friend_ids = []
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        friends = data.get("friendslist", {}).get("friends", [])
        friend_ids = [f["steamid"] for f in friends][:100]
    except Exception as e:
        print(f"Ошибка получения списка друзей: {e}")
        return []
    
    if not friend_ids:
        return []
    
    ids_str = ",".join(friend_ids)
    url2 = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={ids_str}"
    try:
        req = urllib.request.Request(url2)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        players = data.get("response", {}).get("players", [])
    except Exception as e:
        print(f"Ошибка получения статусов друзей: {e}")
        return []
    
    result = []
    for p in players:
        state = p.get("personastate", 0)
        online = state > 0
        current_game = p.get("gameextrainfo", "")
        
        result.append({
            "name": p.get("personaname", "Unknown"),
            "steam_id": p.get("steamid", ""),
            "avatar": p.get("avatarfull", ""),
            "online": online,
            "game": current_game,
            "status": "В сети" if online else "Не в сети",
            "launcher": "Steam",
        })
    
    result.sort(key=lambda x: (not x["game"], not x["online"], x["name"].lower()))
    return result


def get_dummy_friends() -> list:
    return [
        {"name": "API не настроен", "status": "Впиши ключ в friends.py", "game": "", "launcher": "Steam", "online": False, "avatar": ""},
    ]
