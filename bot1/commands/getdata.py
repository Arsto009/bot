from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from settings import is_admin
from backup_manager import get_backup_files


async def get_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # السماح فقط للأدمن
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر خاص بالمطور فقط.")
        return

    files = get_backup_files()

    if not files:
        await update.message.reply_text("⚠ لا توجد نسخ احتياطية حالياً.")
        return

    await update.message.reply_text("📂 جاري إرسال النسخ الاحتياطية...")

    for file_path in files:
        with open(file_path, "rb") as f:
            await update.message.reply_document(document=f)


def register(app):
    app.add_handler(CommandHandler("getdata", get_data_command))
    app.add_handler(CommandHandler("جلب_داتا", get_data_command))