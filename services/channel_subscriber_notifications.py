from services.notifier import notify_subscribers
from services.channel_buttons import build_channel_notification_buttons
from settings import load_config


def _build_bot_ad_link(ad_id):
    if not ad_id:
        return None

    try:
        cfg = load_config()
        bot_username = str(cfg.get("BOT_USERNAME") or "").strip().lstrip("@")
    except Exception:
        bot_username = ""

    if bot_username:
        return f"https://t.me/{bot_username}?start=ad_{ad_id}"

    return None


def _build_channel_post_link(message_id):
    if not message_id:
        return None

    try:
        cfg = load_config()
        channel_username = str(cfg.get("CHANNEL_USERNAME") or "").strip().lstrip("@")
        channel_id = str(cfg.get("CHANNEL_ID") or "").strip()
    except Exception:
        channel_username = ""
        channel_id = ""

    if channel_username:
        return f"https://t.me/{channel_username}/{message_id}"

    if channel_id.startswith("-100"):
        return f"https://t.me/c/{channel_id[4:]}/{message_id}"

    return None


async def notify_new_listing(context, listing, message_id=None, post_link=None):
    text = (listing or {}).get("text", "") or ""
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = lines[0] if lines else "إعلان جديد"

    final_post_link = post_link or _build_channel_post_link(message_id)
    ad_link = _build_bot_ad_link((listing or {}).get("ad_id"))

    try:
        await notify_subscribers(
            context,
            f"🆕 تم إضافة إعلان جديد\n\n{title}",
            ad_link=ad_link,
            extra_buttons=build_channel_notification_buttons(final_post_link)
        )
    except Exception:
        pass


async def notify_updated_listing(context, listing, message_id=None, post_link=None):
    text = (listing or {}).get("text", "") or ""
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = lines[0] if lines else "إعلان تم تعديله"

    final_post_link = post_link or _build_channel_post_link(message_id)
    ad_link = _build_bot_ad_link((listing or {}).get("ad_id"))

    try:
        await notify_subscribers(
            context,
            f"✏️ تم تعديل إعلان\n\n{title}",
            ad_link=ad_link,
            extra_buttons=build_channel_notification_buttons(final_post_link)
        )
    except Exception:
        pass


async def notify_channel_post(context, message):
    if not message:
        return

    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = lines[0] if lines else "يوجد منشور جديد بالقناة"
    post_link = _build_channel_post_link(getattr(message, "message_id", None))

    try:
        await notify_subscribers(
            context,
            f"📢 يوجد إعلان جديد بالقناة\n\n{title}",
            extra_buttons=build_channel_notification_buttons(post_link)
        )
    except Exception:
        pass


async def notify_edited_channel_post(context, message):
    if not message:
        return

    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = lines[0] if lines else "تم تعديل منشور بالقناة"
    post_link = _build_channel_post_link(getattr(message, "message_id", None))

    try:
        await notify_subscribers(
            context,
            f"📝 تم تعديل منشور بالقناة\n\n{title}",
            extra_buttons=build_channel_notification_buttons(post_link)
        )
    except Exception:
        pass
