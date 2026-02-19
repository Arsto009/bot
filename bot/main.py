import importlib
from telegram.ext import Application
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from settings import load_config

config = load_config()
BOT_TOKEN = config.get("BOT_TOKEN")
ADMIN_ID = config.get("ADMIN_ID")


def load_commands(app):
    order = [
    "devpanel",
    "admin",
    "lists",
    "menu_extra",   # 🔥 لازم قبل menu
    "menu",
    "start",
    "help",
    "wizard",
    "search"        # 🔥 search يكون آخر واحد دائماً
]



    for name in order:
        try:
            module = importlib.import_module(f"commands.{name}")
            if hasattr(module, "register"):
                module.register(app)
                print(f"Loaded: {name}.py")
        except Exception as e:
            print(f"❌ Failed to load {name}.py:", e)


async def setup_commands(app):

    public_commands = [
        BotCommand("start", "تشغيل البوت"),
        BotCommand("help", "مساعدة"),
    ]

    admin_commands = [
        BotCommand("add", "إضافة إعلان"),
        BotCommand("add_list", "إضافة لستة"),
        BotCommand("delete_list", "حذف لستة"),
        BotCommand("dev", "لوحة المطور"),
        BotCommand("add_listing", "Wizard إضافة إعلان"),
    ]

    await app.bot.set_my_commands(
        public_commands,
        scope=BotCommandScopeDefault()
    )

    await app.bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_ID)
    )


def main():

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود")
        return

    print("🚀 Bot Starting...")

    app = Application.builder().token(BOT_TOKEN).build()

    load_commands(app)

    app.post_init = setup_commands

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()