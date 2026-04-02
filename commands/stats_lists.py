from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import CallbackQueryHandler

from services.storage import load_data
from services.keyboard import main_menu

stats_message_store = {}



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


def _iter_ads(categories):
    def walk(node, path=""):
        items = node.get("items")
        if isinstance(items, list):
            for ad in items:
                if ad.get("status") == "rented":
                    continue
                yield path, ad

        for key, child in (node.get("sub", {}) or {}).items():
            child_path = f"{path}/{key}" if path else key
            yield from walk(child, child_path)

    root = {"sub": categories}
    yield from walk(root)


def _get_rent_ads(data):
    ads = []
    for path, ad in _iter_ads(data.get("categories", {}) or {}):
        if path.startswith("rent"):
            ads.append(ad)
    return ads


def _get_sale_ads(data):
    ads = []
    for path, ad in _iter_ads(data.get("categories", {}) or {}):
        if path.startswith("sale"):
            ads.append(ad)
    return ads


async def _send_ad_blocks(context, chat_id, ad):
    sent_ids = []
    text = ad.get("text", "") or "بدون نص"

    msg = await context.bot.send_message(chat_id=chat_id, text=text)
    sent_ids.append(msg.message_id)

    media_sequence = _build_media_sequence_from_ad(ad)
    media_chunks = _chunk_media_sequence(media_sequence)

    for chunk in media_chunks:
        try:
            if len(chunk) == 1:
                item = chunk[0]
                if item.get("type") == "photo":
                    m = await context.bot.send_photo(chat_id=chat_id, photo=item.get("file_id"))
                else:
                    m = await context.bot.send_video(chat_id=chat_id, video=item.get("file_id"))
                sent_ids.append(m.message_id)
            else:
                media = []
                for item in chunk:
                    if item.get("type") == "photo":
                        media.append(InputMediaPhoto(item.get("file_id")))
                    else:
                        media.append(InputMediaVideo(item.get("file_id")))
                msgs = await context.bot.send_media_group(chat_id=chat_id, media=media)
                sent_ids.extend([m.message_id for m in msgs])
        except Exception:
            for item in chunk:
                try:
                    if item.get("type") == "photo":
                        m = await context.bot.send_photo(chat_id=chat_id, photo=item.get("file_id"))
                    else:
                        m = await context.bot.send_video(chat_id=chat_id, video=item.get("file_id"))
                    sent_ids.append(m.message_id)
                except Exception:
                    pass

    return sent_ids


async def _show_stats_list(update, context, mode):
    query = update.callback_query
    await query.answer()

    data = load_data()
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    old_ids = stats_message_store.pop(user_id, [])
    for mid in old_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
    except Exception:
        pass

    if mode == "rent":
        ads = _get_rent_ads(data)
        title = f"📊 عدد اعلانات الايجار: {len(ads)}"
    else:
        ads = _get_sale_ads(data)
        title = f"📊 عدد اعلان البيع: {len(ads)}"

    sent_ids = []

    for ad in ads:
        sent_ids.extend(await _send_ad_blocks(context, chat_id, ad))

    footer = await context.bot.send_message(
        chat_id=chat_id,
        text=f"{title}\n\nانتهت الإعلانات.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏮ القائمة الرئيسية", callback_data="stats:back_main")]
        ])
    )
    sent_ids.append(footer.message_id)

    stats_message_store[user_id] = sent_ids


async def show_rent_stats(update, context):
    await _show_stats_list(update, context, "rent")


async def show_sale_stats(update, context):
    await _show_stats_list(update, context, "sale")


async def stats_back_main(update, context):
    query = update.callback_query
    await query.answer()

    data = load_data()
    categories = data.get("categories", {})
    phones = data.get("info", {}).get("phones", [])
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    current_message_id = query.message.message_id

    old_ids = stats_message_store.pop(user_id, [])
    for mid in old_ids:
        if mid == current_message_id:
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

    try:
        await query.message.edit_text(
            f"🏢 {data['info']['business_name']}\n\n"
            f"📍 {data['info']['address']}\n\n"
            f"📞 أرقام التواصل:\n" +
            "\n".join(data["info"]["phones"]) +
            "\n\nاختر وسيلة التواصل أو القسم:",
            reply_markup=main_menu(categories, phones, True)
        )
    except Exception:
        pass


def register(app):
    app.add_handler(CallbackQueryHandler(show_rent_stats, pattern=r"^stats_rent$"), group=49)
    app.add_handler(CallbackQueryHandler(show_sale_stats, pattern=r"^stats_sale$"), group=49)
    app.add_handler(CallbackQueryHandler(stats_back_main, pattern=r"^stats:back_main$"), group=49)
