import importlib

from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from settings import load_config
from services.channel_post_listener import handle_direct_channel_post
from services.channel_buttons import handle_notification_action


def load_commands(app):

    order = [
        "devpanel",
        "admin",
        "lists",
        "menu_extra",
        "stats_lists",
        "menu",
        "start",
        "help",
        "wizard",
        "data_listings",
        "rented_manager",
        "smart_inbox",
        "dashboard",
        "report",
        "search",
    ]

    for name in order:
        try:
            module = importlib.import_module(f"commands.{name}")

            if hasattr(module, "register"):
                module.register(app)
                print(f"Loaded: {name}.py")

        except Exception as e:
            print(f"❌ Failed to load {name}.py:", e)


def build_commands(commands_list):
    cmds = []
    for item in commands_list:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            cmds.append(BotCommand(item[0], item[1]))
    return cmds


async def setup_commands(app):

    config = load_config()

    ADMIN_ID = config.get("ADMIN_ID")
    ADMINS = config.get("ADMINS", [])

    try:
        ADMIN_ID = int(ADMIN_ID)
    except (TypeError, ValueError):
        ADMIN_ID = None

    admins_clean = []

    for a in ADMINS:
        try:
            admins_clean.append(int(a))
        except:
            pass

    public_commands = build_commands(
        config.get("PUBLIC_COMMANDS", [])
    )

    admin_commands = build_commands(
        config.get("ADMIN_COMMANDS", [])
    )

    await app.bot.delete_my_commands()

    await app.bot.set_my_commands(
        public_commands,
        scope=BotCommandScopeDefault()
    )

    all_admins = []

    if ADMIN_ID:
        all_admins.append(ADMIN_ID)

    for a in admins_clean:
        if a not in all_admins:
            all_admins.append(a)

    for admin_id in all_admins:
        try:
            await app.bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception:
            pass


def main():

    config = load_config()

    BOT_TOKEN = config.get("BOT_TOKEN")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود")
        return

    print("🚀 Bot Starting...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(60)
        .write_timeout(60)
        .pool_timeout(30)
        .build()
    )

    load_commands(app)

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_direct_channel_post), group=99)
    app.add_handler(CallbackQueryHandler(handle_notification_action, pattern="^ignore_notification$"), group=99)

    app.post_init = setup_commands

    print("✅ Bot is running...")

    app.run_polling(allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"])


if __name__ == "__main__":
    main()
