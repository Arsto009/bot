from settings import load_config
from services.channel_subscriber_notifications import notify_channel_post, notify_edited_channel_post


def _channel_id():
    cfg = load_config()
    return cfg.get("CHANNEL_ID")


def _enabled():
    cfg = load_config()
    return bool(cfg.get("CHANNEL_SYNC_ENABLED")) and bool(_channel_id())


async def handle_direct_channel_post(update, context):
    if not _enabled():
        return

    message = getattr(update, "channel_post", None)
    edited_message = getattr(update, "edited_channel_post", None)

    if message:
        sender = getattr(message, "from_user", None)
        if sender and getattr(sender, "is_bot", False):
            return

        await notify_channel_post(context, message)
        return

    if edited_message:
        sender = getattr(edited_message, "from_user", None)
        if sender and getattr(sender, "is_bot", False):
            return

        await notify_edited_channel_post(context, edited_message)
