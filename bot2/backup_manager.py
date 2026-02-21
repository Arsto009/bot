import os

BACKUP_DIR = "backups"
PREV_FILE = os.path.join(BACKUP_DIR, "listings_PREV.json")
CURR_FILE = os.path.join(BACKUP_DIR, "listings_CURR.json")

def get_backup_files(limit: int = 2):
    os.makedirs(BACKUP_DIR, exist_ok=True)

    files = []
    if os.path.exists(PREV_FILE):
        files.append(PREV_FILE)
    if os.path.exists(CURR_FILE):
        files.append(CURR_FILE)

    # يرجع بالترتيب: قبل التعديل ثم بعد التعديل
    return files[:limit]