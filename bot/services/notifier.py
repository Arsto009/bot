from pathlib import Path
import json
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.channel_buttons import build_channel_notification_buttons
from services.channel_post_links import get_channel_post_link

BASE_DIR = Path(__file__).resolve().parent.parent
SUBSCRIBERS_FILE = BASE_DIR / "data" / "subscribers.json"


def load_subscribers() -> List[int]:
    if not SUBSCRIBERS_FILE.exists():
        SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SUBSCRIBERS_FILE.write_text("[]", encoding="utf-8")
        return []

    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            clean = []
            for x in data:
                try:
                    clean.append(int(x))
                except Exception:
                    pass
            return clean
        return []
    except Exception:
        return []


def save_subscribers(subscribers: List[int]):
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_FILE.write_text(
        json.dumps(sorted(list(set(subscribers))), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_subscriber(user_id: int):
    subscribers = load_subscribers()
    if user_id not in subscribers:
        subscribers.append(user_id)
        save_subscribers(subscribers)


def remove_subscriber(user_id: int):
    subscribers = load_subscribers()
    if user_id in subscribers:
        subscribers.remove(user_id)
        save_subscribers(subscribers)


def _extract_ad_id_from_link(ad_link: str | None):
    if not ad_link:
        return None

    marker = "start=ad_"
    if marker not in ad_link:
        return None

    return ad_link.split(marker, 1)[1].split("&", 1)[0].strip() or None


def _build_rows_for_ads(ads):
    keyboard = []
    if not ads:
        return keyboard

    for i, ad in enumerate(ads, start=1):
        if not isinstance(ad, dict):
            continue

        ad_link = ad.get("ad_link")
        if not ad_link and ad.get("ad_id"):
            ad_link = f"https://t.me/{{BOT_USERNAME_PLACEHOLDER}}?start=ad_{ad.get('ad_id')}"

        ad_id = ad.get("ad_id") or _extract_ad_id_from_link(ad_link)
        post_link = ad.get("post_link") or get_channel_post_link(ad_id)

        row = []
        if ad_link:
            row.append(InlineKeyboardButton(f"📌 عرض {i}", url=ad_link))
        if post_link:
            row.append(InlineKeyboardButton(f"إظهار {i}", url=post_link))

        if row:
            keyboard.append(row)

    if keyboard:
        keyboard.append([InlineKeyboardButton("تجاهل", callback_data="ignore_notification")])

    return keyboard


async def notify_subscribers(context, text: str, ad_link: str | None = None, extra_buttons=None, ads=None):
    subscribers = load_subscribers()

    reply_markup = None
    keyboard = []

    if ads:
        keyboard = _build_rows_for_ads(ads)
    else:
        if ad_link:
            keyboard.append([InlineKeyboardButton("📌 عرض الإعلان", url=ad_link)])

        if not extra_buttons and ad_link:
            ad_id = _extract_ad_id_from_link(ad_link)
            channel_post_link = get_channel_post_link(ad_id)
            extra_buttons = build_channel_notification_buttons(channel_post_link)

        if extra_buttons:
            for row in extra_buttons:
                if row:
                    keyboard.append(row)

    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)

    dead_users = []

    for user_id in subscribers:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                disable_notification=True
            )
        except Exception:
            dead_users.append(user_id)

    if dead_users:
        for uid in dead_users:
            remove_subscriber(uid)
