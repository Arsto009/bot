import importlib
import os
import sys

from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application

from settings import load_config


# Ensure imports work no matter where the bot is launched from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def load_commands(app: Application):
    order = [
        "devpanel",
        "admin",
        "lists",
        "menu_extra",  # لازم قبل menu
        "menu",
        "start",
        "help",
        "wizard",
        "getdata",
        "search",  # search يكون آخر واحد
    ]

    for name in order:
        try:
            module = importlib.import_module(f"commands.{name}")
            if hasattr(module, "register"):
                module.register(app)
                print(f"Loaded: {name}.py")
        except Exception as e:
            print(f"❌ Failed to load {name}.py: {e}")


async def setup_commands(app: Application):
    config = load_config()
    admin_id = config.get("ADMIN_ID")

    await app.bot.delete_my_commands()

    public_commands = [
        BotCommand("start", "تشغيل البوت"),
        BotCommand("help", "مساعدة"),
    ]

    admin_commands = [
        BotCommand("start", "تشغيل البوت"),
        BotCommand("add", "إضافة إعلان"),
        BotCommand("getdata", "إرسال آخر نسختين احتياطية"),
    ]

    await app.bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())

    # IMPORTANT: BotCommandScopeChat requires an int chat_id
    if isinstance(admin_id, int):
        await app.bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )


def main():
    config = load_config()
    bot_token = config.get("BOT_TOKEN")

    if not bot_token:
        print("❌ BOT_TOKEN غير موجود. ضعه في ENV (BOT_TOKEN) أو داخل config.json")
        return

    print("🚀 Bot Starting...")

    app = Application.builder().token(bot_token).build()

    load_commands(app)

    app.post_init = setup_commands

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
