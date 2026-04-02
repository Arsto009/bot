import os
import shutil
from datetime import datetime

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from settings import is_admin


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # bot/
DATA_FILE = os.path.join(BASE_DIR, "data", "listings.json")

BACKUP_DIR = os.path.join(BASE_DIR, "data", "_snapshots")
BEFORE_FILE = os.path.join(BACKUP_DIR, "listings_before.json")
AFTER_FILE = os.path.join(BACKUP_DIR, "listings_after.json")


def _ensure_dirs():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _rotate_snapshots():
    _ensure_dirs()

    # حذف before القديم
    if os.path.exists(BEFORE_FILE):
        try:
            os.remove(BEFORE_FILE)
        except:
            pass

    # ترحيل after إلى before
    if os.path.exists(AFTER_FILE):
        try:
            os.replace(AFTER_FILE, BEFORE_FILE)
        except:
            try:
                shutil.move(AFTER_FILE, BEFORE_FILE)
            except:
                pass

    # إنشاء after جديد من listings الحالي
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, AFTER_FILE)
    else:
        raise FileNotFoundError(f"Missing listings file: {DATA_FILE}")


async def data_listings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر خاص بالإدارة فقط.")
        return

    try:
        _rotate_snapshots()
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ أثناء عمل النسخ: {e}")
        return

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if os.path.exists(BEFORE_FILE):
        with open(BEFORE_FILE, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"listings_BEFORE_{ts}.json",
                caption="📦 نسخة قبل التعديل (من المرة السابقة)"
            )
    else:
        await update.message.reply_text("ℹ️ لا توجد نسخة BEFORE بعد (هذه أول مرة).")

    if os.path.exists(AFTER_FILE):
        with open(AFTER_FILE, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"listings_AFTER_{ts}.json",
                caption="✅ نسخة بعد التعديل (الحالية الآن)"
            )


def register(app):
    app.add_handler(CommandHandler("data_listings", data_listings_command))
    app.add_handler(CommandHandler("datad_listings", data_listings_command))