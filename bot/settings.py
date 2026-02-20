import json
import os

CONFIG_FILE = "config.json"

# =========================
# تحميل الإعدادات
# =========================
def load_config():
    # لو الملف غير موجود، نسوي default
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "ADMIN_ID": "",   # خليه فارغ بالبداية
            "BOT_TOKEN": "",
            "BOT_PASSWORD": "",
            "ADMINS": []
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config

    # قراءة الملف
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# =========================
# حفظ الإعدادات
# =========================
def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =========================
# تحميل إعدادات ADMIN_ID و BOT_TOKEN
# =========================
_config = load_config()

# ADMIN_ID: من ENV أو config.json
ADMIN_ID = os.getenv("ADMIN_ID") or _config.get("ADMIN_ID")
try:
    ADMIN_ID = int(ADMIN_ID)
except (TypeError, ValueError):
    raise ValueError("❌ ADMIN_ID must be a valid integer!")

# BOT_TOKEN: من ENV أو config.json
BOT_TOKEN = os.getenv("BOT_TOKEN") or _config.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing! Set it in config.json or ENV variable.")

# قائمة ADMINS إضافية
ADMINS = _config.get("ADMINS", [])

# =========================
# فحص الأدمن
# =========================
def is_admin(user_id):
    return user_id == ADMIN_ID or user_id in ADMINS

# =========================
# اختبار التحميل
# =========================
if __name__ == "__main__":
    print("✅ Settings loaded successfully!")
    print(f"ADMIN_ID: {ADMIN_ID}")
    print(f"BOT_TOKEN: {BOT_TOKEN[:5]}... (hidden)")
    print(f"ADMINS: {ADMINS}")
