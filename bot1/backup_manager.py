import os
import shutil
from datetime import datetime

SOURCE_FILE = os.path.join("data", "listings.json")
BACKUP_DIR = "backups"

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup() -> bool:
    """
    ينشئ نسخة احتياطية من data/listings.json داخل backups/
    """
    ensure_backup_dir()

    if not os.path.exists(SOURCE_FILE):
        return False

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"listings_{ts}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy2(SOURCE_FILE, backup_path)
    return True

def get_backup_files(limit: int = 2):
    """
    يرجع آخر نسخ احتياطية حسب الاسم (الأحدث آخر شي).
    limit=2 يعني آخر نسختين
    """
    ensure_backup_dir()

    files = []
    for name in os.listdir(BACKUP_DIR):
        if name.startswith("listings_") and name.endswith(".json"):
            files.append(os.path.join(BACKUP_DIR, name))

    # ترتيب حسب الاسم (لأن الاسم يحتوي timestamp)
    files.sort()
    return files[-limit:]