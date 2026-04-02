from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
POST_LINKS_FILE = BASE_DIR / "data" / "channel_post_links.json"


def _ensure_file():
    if not POST_LINKS_FILE.exists():
        POST_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        POST_LINKS_FILE.write_text("{}", encoding="utf-8")


def load_channel_post_links():
    _ensure_file()
    try:
        data = json.loads(POST_LINKS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_channel_post_links(data):
    POST_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POST_LINKS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def set_channel_post_link(ad_id, post_link):
    if not ad_id:
        return

    data = load_channel_post_links()
    data[str(ad_id)] = post_link
    save_channel_post_links(data)


def get_channel_post_link(ad_id):
    if not ad_id:
        return None

    data = load_channel_post_links()
    return data.get(str(ad_id))


def remove_channel_post_link(ad_id):
    if not ad_id:
        return

    data = load_channel_post_links()
    if str(ad_id) in data:
        del data[str(ad_id)]
        save_channel_post_links(data)
