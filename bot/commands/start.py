from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
import uuid

from services.storage import load_data, save_data
from services.keyboard import main_menu
from settings import load_config
from services.notifier import add_subscriber

SEEN_CACHE = {}


def _build_media_sequence_from_ad(ad):
    raw = ad.get("media_sequence", []) or []
    seq = []
    seen = set()

    for item in raw:
        if not isinstance(item, dict):
            continue
        media_type = item.get("type")
        file_id = item.get("file_id")
        media_group_id = item.get("media_group_id")
        if media_type not in ("photo", "video") or not file_id:
            continue
        key = (media_type, file_id, media_group_id)
        if key in seen:
            continue
        seen.add(key)
        seq.append({
            "type": media_type,
            "file_id": file_id,
            "media_group_id": media_group_id,
        })

    if seq:
        return seq

    for p in ad.get("photos", []) or []:
        seq.append({"type": "photo", "file_id": p, "media_group_id": None})
    for v in ad.get("videos", []) or []:
        seq.append({"type": "video", "file_id": v, "media_group_id": None})
    return seq


def _chunk_media_sequence(seq):
    chunks = []
    current = []
    for item in seq:
        if not current:
            current = [item]
            continue

        prev = current[-1]
        same_group = (
            prev.get("media_group_id")
            and item.get("media_group_id")
            and prev.get("media_group_id") == item.get("media_group_id")
        )

        if same_group and len(current) < 10:
            current.append(item)
        else:
            chunks.append(current)
            current = [item]

    if current:
        chunks.append(current)
    return chunks


def _find_ad_by_id(data, ad_id):
    categories = data.get("categories", {}) or {}

    def walk(node):
        subs = node.get("sub", {}) or {}
        items = node.get("items", None)

        if isinstance(items, list):
            for it in items:
                if str(it.get("ad_id", "")) == str(ad_id):
                    return it

        for child in subs.values():
            found = walk(child)
            if found:
                return found
        return None

    root = {"sub": categories}
    return walk(root)


def _increase_ad_views(data, ad_id, user_id):
    categories = data.get("categories", {}) or {}

    def walk(node):
        subs = node.get("sub", {}) or {}
        items = node.get("items", None)

        if isinstance(items, list):
            for it in items:
                if str(it.get("ad_id", "")) == str(ad_id):
                    it.setdefault("viewers", [])
                    if user_id not in it["viewers"]:
                        it["viewers"].append(user_id)
                        it["views"] = len(it["viewers"])
                        return True
                    return False

        for child in subs.values():
            if walk(child):
                return True
        return False

    root = {"sub": categories}
    return walk(root)


async def _send_ad(update, context, ad):
    text = ad.get("text", "") or "بدون نص"
    sent_ids = []
    cache_id = uuid.uuid4().hex[:12]

    msg = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تمت الرؤية", callback_data=f"seen:{cache_id}")]
        ])
    )
    sent_ids.append(msg.message_id)

    media_sequence = _build_media_sequence_from_ad(ad)
    media_chunks = _chunk_media_sequence(media_sequence)

    for chunk in media_chunks:
        try:
            if len(chunk) == 1:
                item = chunk[0]
                if item.get("type") == "photo":
                    m = await update.message.reply_photo(photo=item.get("file_id"))
                else:
                    m = await update.message.reply_video(video=item.get("file_id"))
                sent_ids.append(m.message_id)
            else:
                media = []
                for item in chunk:
                    if item.get("type") == "photo":
                        media.append(InputMediaPhoto(item.get("file_id")))
                    else:
                        media.append(InputMediaVideo(item.get("file_id")))
                msgs = await update.message.reply_media_group(media)
                sent_ids.extend([m.message_id for m in msgs])
        except Exception:
            for item in chunk:
                try:
                    if item.get("type") == "photo":
                        m = await update.message.reply_photo(photo=item.get("file_id"))
                    else:
                        m = await update.message.reply_video(video=item.get("file_id"))
                    sent_ids.append(m.message_id)
                except Exception:
                    pass

    SEEN_CACHE[cache_id] = {
        "chat_id": update.effective_chat.id,
        "message_ids": sent_ids,
    }


async def seen_callback(update, context):
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    if not data.startswith("seen:"):
        return

    cache_id = data.split(":", 1)[1]
    item = SEEN_CACHE.pop(cache_id, None)

    if not item:
        try:
            await q.message.delete()
        except Exception:
            try:
                await q.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    chat_id = item["chat_id"]
    message_ids = item["message_ids"]

    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

    try:
        await q.message.delete()
    except Exception:
        try:
            await q.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


async def start(update, context):
    data = load_data()
    config = load_config()
    add_subscriber(update.effective_user.id)
    ADMIN_ID = config.get("ADMIN_ID")

    try:
        ADMIN_ID = int(ADMIN_ID)
    except (TypeError, ValueError):
        ADMIN_ID = None

    args = context.args or []
    if args:
        payload = str(args[0]).strip()
        if payload.startswith("ad_"):
            ad_id = payload.replace("ad_", "", 1).strip()
            ad = _find_ad_by_id(data, ad_id)
            if ad:
                if _increase_ad_views(data, ad_id, update.effective_user.id):
                    save_data(data)
                    ad = _find_ad_by_id(data, ad_id)
                await _send_ad(update, context, ad)
                return
            else:
                await update.message.reply_text("❌ الإعلان غير موجود أو تم حذفه.")
                return

    info = data.get("info", {})
    phones = info.get("phones", [])

    phone_list = "\n".join([f"{i+1}) {p}" for i, p in enumerate(phones)]) if phones else "لا يوجد"

    text = (
        f"🏢 {info.get('business_name', 'عقارات')}\n\n"
        f"📍 {info.get('address', '---')}\n\n"
        f"📞 أرقام التواصل:\n{phone_list}\n\n"
        "اختر وسيلة التواصل أو القسم:"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu(
            data.get("categories", {}),
            phones,
            update.effective_user.id == ADMIN_ID or update.effective_user.id in config.get("ADMINS", [])
        )
    )


def register(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(seen_callback, pattern=r"^seen:"))
