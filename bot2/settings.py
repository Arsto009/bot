import json
import os
from typing import Any, Dict, List, Union

CONFIG_FILE = os.getenv("BOT_CONFIG_FILE", "config.json")


def _to_int(value) -> Union[int, None]:
    """Convert value to int safely."""
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _to_int_list(values) -> List[int]:
    out: List[int] = []
    if not values:
        return out
    for v in values:
        i = _to_int(v)
        if i is not None:
            out.append(i)
    return out


def load_config() -> Dict[str, Any]:
    default_config = {
        "ADMIN_ID": "",
        "BOT_TOKEN": "",
        "BOT_PASSWORD": "",
        "ADMINS": [],
    }

    if not os.path.exists(CONFIG_FILE):
        # create a fresh config file if missing
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        config = dict(default_config)
    else:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

    # ENV overrides (Railway / Render / etc.)
    env_token = os.getenv("BOT_TOKEN")
    if env_token:
        config["BOT_TOKEN"] = env_token.strip()

    env_admin_id = os.getenv("ADMIN_ID")
    if env_admin_id:
        config["ADMIN_ID"] = env_admin_id.strip()

    env_admins = os.getenv("ADMINS")  # optional: "111,222,333"
    if env_admins:
        config["ADMINS"] = [x.strip() for x in env_admins.split(",") if x.strip()]

    # Normalize types
    config["ADMIN_ID"] = _to_int(config.get("ADMIN_ID")) or ""
    config["ADMINS"] = _to_int_list(config.get("ADMINS", []))

    return config


def save_config(data: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_admin(user_id: int) -> bool:
    config = load_config()
    return (
        user_id == config.get("ADMIN_ID")
        or user_id in config.get("ADMINS", [])
    )
