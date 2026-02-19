from telegram.ext import CommandHandler
from services.storage import load_data
from services.keyboard import main_menu
from settings import load_config


async def start(update, context):
    data = load_data()
    config = load_config()
    ADMIN_ID = config.get("ADMIN_ID")

    info = data["info"]
    phones = info["phones"]

    phone_list = "\n".join([f"{i+1}) {p}" for i, p in enumerate(phones)])

    text = (
        f"🏢 {info['business_name']}\n\n"
        f"📍 {info['address']}\n\n"
        f"📞 أرقام التواصل:\n{phone_list}\n\n"
        "اختر وسيلة التواصل أو القسم:"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu(
            data["categories"],
            phones,
            update.effective_user.id == ADMIN_ID
        )
    )


def register(app):
    app.add_handler(CommandHandler("start", start))