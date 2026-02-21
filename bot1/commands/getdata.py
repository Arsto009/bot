from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from settings import is_admin
from backup_manager import get_backup_files


async def send_last_two_backups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    files = get_backup_files(limit=2)

    if not files:
        await update.message.reply_text("⚠ لا توجد نسخ احتياطية حالياً.")
        return

    if len(files) == 1:
        await update.message.reply_text("📦 توجد نسخة واحدة فقط، سأرسلها الآن.")
    else:
        await update.message.reply_text("📦 سأرسل آخر نسختين: قبل التعديل + بعد التعديل.")

    for file_path in files:
        with open(file_path, "rb") as f:
            await update.message.reply_document(document=f)


async def get_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_last_two_backups(update, context)


async def get_data_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if update.message.text.strip().lower() == "data1":
        await send_last_two_backups(update, context)


def register(app):
    app.add_handler(CommandHandler("getdata", get_data_command))
    app.add_handler(CommandHandler("data1", get_data_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_data_text), group=20)