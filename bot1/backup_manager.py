import os
import shutil

DATA_FOLDER = "data"
SOURCE_FILE = os.path.join(DATA_FOLDER, "listings.json")

BEFORE_FILE = os.path.join(DATA_FOLDER, "listings_before.json")
AFTER_FILE = os.path.join(DATA_FOLDER, "listings_after.json")


def create_smart_backup():
    """
    نظام ذكي:
    - إذا يوجد after → يتحول إلى before
    - إذا يوجد before قديم → ينحذف
    """

    if not os.path.exists(SOURCE_FILE):
        return False

    # إذا يوجد before قديم → احذفه
    if os.path.exists(BEFORE_FILE):
        os.remove(BEFORE_FILE)

    # إذا يوجد after → حوله إلى before
    if os.path.exists(AFTER_FILE):
        shutil.move(AFTER_FILE, BEFORE_FILE)
    else:
        # أول مرة → انسخ المصدر إلى before
        shutil.copy2(SOURCE_FILE, BEFORE_FILE)

    return True


def save_new_version():
    """
    بعد التعديل نحفظ النسخة الجديدة كـ after
    """

    if not os.path.exists(SOURCE_FILE):
        return False

    shutil.copy2(SOURCE_FILE, AFTER_FILE)
    return True


def get_backup_files():
    files = []

    if os.path.exists(BEFORE_FILE):
        files.append(BEFORE_FILE)

    if os.path.exists(AFTER_FILE):
        files.append(AFTER_FILE)

    return files