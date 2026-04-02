import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = str(BASE_DIR / "config.json")

if load_dotenv is not None:
    load_dotenv(str(BASE_DIR / ".env"))


def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "ADMIN_ID": "",
            "BOT_TOKEN": "",
            "BOT_PASSWORD": "",
            "ADMINS": [],
            "BOT_USERNAME": "",
            "ADMIN_COMMANDS": [
                ["start", "تشغيل البوت"],
                ["data_listings", "ملفات الداتا"],
                ["report", "تقرير Word"],
                ["dashboard", "لوحة الإحصائيات"],
                ["open_comments_all", "فتح التعليقات للكل"],
                ["close_comments_all", "غلق التعليقات للكل"]
            ],
            "PUBLIC_COMMANDS": [
                ["start", "تشغيل البوت"],
                ["help", "مساعدة"]
            ]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_config = load_config()

ADMIN_ID = os.getenv("ADMIN_ID") or _config.get("ADMIN_ID")
try:
    ADMIN_ID = int(ADMIN_ID)
except (TypeError, ValueError):
    raise ValueError("❌ ADMIN_ID must be a valid integer!")

BOT_TOKEN = os.getenv("BOT_TOKEN") or _config.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing! Set it in config.json or ENV variable.")

ADMINS = _config.get("ADMINS", [])


def is_admin(user_id):
    return user_id == ADMIN_ID or user_id in ADMINS


if __name__ == "__main__":
    print("✅ Settings loaded successfully!")
    print(f"ADMIN_ID: {ADMIN_ID}")
    print(f"BOT_TOKEN: {BOT_TOKEN[:5]}... (hidden)")
    print(f"ADMINS: {ADMINS}")
