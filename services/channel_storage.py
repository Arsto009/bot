from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_MAP_FILE = BASE_DIR / "data" / "channel_posts.json"


def load_channel_posts():
    if not CHANNEL_MAP_FILE.exists():
        CHANNEL_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHANNEL_MAP_FILE.write_text("{}", encoding="utf-8")
        return {}

    try:
        data = json.loads(CHANNEL_MAP_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_channel_posts(data):
    CHANNEL_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNEL_MAP_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_channel_post(ad_id):
    return load_channel_posts().get(str(ad_id), {})


def set_channel_post(ad_id, payload):
    data = load_channel_posts()
    data[str(ad_id)] = payload
    save_channel_posts(data)


def remove_channel_post(ad_id):
    data = load_channel_posts()
    data.pop(str(ad_id), None)
    save_channel_posts(data)
