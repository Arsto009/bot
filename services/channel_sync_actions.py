import asyncio
from pathlib import Path
from datetime import datetime

from telegram import InputMediaPhoto, InputMediaVideo
from telegram.error import TimedOut, RetryAfter

from settings import load_config
from services.storage import load_data
from services.channel_storage import get_channel_post, set_channel_post, remove_channel_post
from services.channel_post_links import set_channel_post_link, remove_channel_post_link
from services.channel_subscriber_notifications import notify_new_listing, notify_updated_listing


CHANNEL_PUBLISH_LOCK = asyncio.Lock()
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG_LOG_FILE = BASE_DIR / "data" / "channel_sync_debug.log"


def _cfg():
    return load_config()


def _channel_id_raw():
    return _cfg().get("CHANNEL_ID")


def _channel_id():
    channel_id = _channel_id_raw()
    if channel_id is None:
        return None
    channel_id = str(channel_id).strip()
    if not channel_id:
        return None
    if channel_id.startswith("@"):
        return channel_id
    try:
        return int(channel_id)
    except Exception:
        return channel_id


def _enabled():
    cfg = _cfg()
    return bool(cfg.get("CHANNEL_SYNC_ENABLED")) and bool(_channel_id())


def _channel_username():
    cfg = _cfg()
    return cfg.get("CHANNEL_USERNAME")


def _admin_id():
    value = _cfg().get("ADMIN_ID")
    try:
        return int(value)
    except Exception:
        return None


def _log_debug(message):
    DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with DEBUG_LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(f'[{stamp}] {message}\n')
        f.write(f'[{stamp}] {message}\n')
    print(message)


async def _notify_admin(context, text):
    admin_id = _admin_id()
    if not admin_id:
        return
    try:
        await context.bot.send_message(chat_id=admin_id, text=text[:4000])
    except Exception:
        pass




async def _bot_call_with_retry(call, *args, **kwargs):
    last_error = None
    for attempt in range(4):
        try:
            return await call(*args, **kwargs)
        except RetryAfter as e:
            wait_time = int(getattr(e, "retry_after", 3) or 3) + 1
            _log_debug(f"retry_after wait={wait_time}s call={getattr(call, '__name__', str(call))} attempt={attempt+1}")
            await asyncio.sleep(wait_time)
            last_error = e
        except TimedOut as e:
            wait_time = min(2 * (attempt + 1), 8)
            _log_debug(f"timeout wait={wait_time}s call={getattr(call, '__name__', str(call))} attempt={attempt+1}")
            await asyncio.sleep(wait_time)
            last_error = e
    if last_error:
        raise last_error
    return await call(*args, **kwargs)

def _build_post_link(message_id):
    if not message_id:
        return None

    username = _channel_username()
    if username:
        username = str(username).strip().lstrip("@")
        if username:
            return f"https://t.me/{username}/{message_id}"

    channel_id = str(_channel_id_raw() or "").strip()
    if channel_id.startswith("-100"):
        internal_id = channel_id.replace("-100", "", 1)
        return f"https://t.me/c/{internal_id}/{message_id}"

    return None


def _iter_items(categories, prefix=""):
    for key, node in (categories or {}).items():
        path = f"{prefix}/{key}" if prefix else key

        for item in node.get("items", []) or []:
            yield path, item

        for child_path, child_item in _iter_items(node.get("sub", {}) or {}, path):
            yield child_path, child_item


def _find_listing_in_storage(ad_id):
    if not ad_id:
        return None, None

    data = load_data()
    categories = data.get("categories", {}) or {}

    smart_item = None

    for path, item in _iter_items(categories):
        if item.get("ad_id") != ad_id:
            continue

        if path == "smart_inbox":
            smart_item = item
            continue

        return item, path

    if smart_item:
        return smart_item, "smart_inbox"

    return None, None


def _resolve_channel_listing(listing):
    if not listing:
        return None, None

    ad_id = listing.get("ad_id")
    if not ad_id:
        return None, None

    stored_item, stored_path = _find_listing_in_storage(ad_id)

    if stored_item and stored_path != "smart_inbox":
        if stored_item.get("status") == "rented":
            return None, stored_path
        return stored_item, stored_path

    if stored_path == "smart_inbox":
        return None, stored_path

    if listing.get("status") == "rented":
        return None, None

    return listing, None


async def _delete_known_messages(context, post_data):
    if not post_data:
        return

    channel_id = _channel_id()
    message_ids = post_data.get("message_ids", []) or []

    for message_id in message_ids:
        try:
            await _bot_call_with_retry(context.bot.delete_message, chat_id=channel_id, message_id=message_id)
        except Exception as e:
            _log_debug(f"delete_message failed chat_id={channel_id} message_id={message_id}: {e}")


async def _delete_listing_from_channel_unlocked(context, ad_id):
    if not _enabled() or not ad_id:
        return

    post_data = get_channel_post(ad_id)
    await _delete_known_messages(context, post_data)
    remove_channel_post(ad_id)
    remove_channel_post_link(ad_id)


def _build_media_sequence_from_legacy(listing):
    sequence = []

    for p in listing.get("photos", []) or []:
        sequence.append({
            "type": "photo",
            "file_id": p,
            "media_group_id": None,
        })

    for v in listing.get("videos", []) or []:
        sequence.append({
            "type": "video",
            "file_id": v,
            "media_group_id": None,
        })

    return sequence


def _normalized_media_sequence(listing):
    raw = listing.get("media_sequence", []) or []
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

    return _build_media_sequence_from_legacy(listing)


def _chunked_media_sequence(seq):
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
            continue

        chunks.append(current)
        current = [item]

    if current:
        chunks.append(current)

    return chunks


async def _send_single_media(context, channel_id, item, caption=None):
    if item.get("type") == "photo":
        return await _bot_call_with_retry(context.bot.send_photo, chat_id=channel_id, photo=item.get("file_id"), caption=caption)
    return await _bot_call_with_retry(context.bot.send_video, chat_id=channel_id, video=item.get("file_id"), caption=caption)


async def _send_media_chunk(context, channel_id, chunk, caption=None):
    if not chunk:
        return []

    if len(chunk) == 1:
        msg = await _send_single_media(context, channel_id, chunk[0], caption=caption)
        return [msg]

    media = []
    for idx, item in enumerate(chunk):
        item_caption = caption if idx == 0 else None
        if item.get("type") == "photo":
            media.append(InputMediaPhoto(media=item.get("file_id"), caption=item_caption))
        else:
            media.append(InputMediaVideo(media=item.get("file_id"), caption=item_caption))

    msgs = await _bot_call_with_retry(context.bot.send_media_group, chat_id=channel_id, media=media)
    return list(msgs)


async def publish_listing_to_channel(context, listing, notify_guests=True, notify_as_update=False):
    if not _enabled() or not listing:
        return

    ad_id = listing.get("ad_id")
    if not ad_id:
        return

    async with CHANNEL_PUBLISH_LOCK:
        final_listing, final_path = _resolve_channel_listing(listing)

        if final_path == "smart_inbox":
            return

        if not final_listing:
            await _delete_listing_from_channel_unlocked(context, ad_id)
            return

        await _delete_listing_from_channel_unlocked(context, ad_id)

        channel_id = _channel_id()
        text = (final_listing.get("text", "") or "بدون نص").strip()
        message_ids = []
        media_sequence = _normalized_media_sequence(final_listing)
        media_chunks = _chunked_media_sequence(media_sequence)

        _log_debug(f"publish start ad_id={ad_id} channel_id={channel_id} media_items={len(media_sequence)}")

        try:
            text_msg = await _bot_call_with_retry(context.bot.send_message, chat_id=channel_id, text=text)
            message_ids.append(text_msg.message_id)
            await asyncio.sleep(0.6)

            for chunk in media_chunks:
                msgs = await _send_media_chunk(context, channel_id, chunk)
                message_ids.extend([m.message_id for m in msgs])
                await asyncio.sleep(0.8)
        except Exception as e:
            err = f"❌ فشل نشر الإعلان للقناة\nad_id: {ad_id}\nchannel_id: {channel_id}\nerror: {e}"
            _log_debug(err)
            await _notify_admin(context, err)
            return

        post_link = _build_post_link(message_ids[0])
        set_channel_post(ad_id, {"message_ids": message_ids})
        set_channel_post_link(ad_id, post_link)
        _log_debug(f"publish success ad_id={ad_id} message_ids={message_ids}")

        if notify_guests:
            try:
                if notify_as_update:
                    await notify_updated_listing(context, final_listing, message_id=message_ids[0], post_link=post_link)
                else:
                    await notify_new_listing(context, final_listing, message_id=message_ids[0], post_link=post_link)
            except Exception as e:
                _log_debug(f"notify guests failed ad_id={ad_id}: {e}")


async def delete_listing_from_channel(context, ad_id):
    if not _enabled() or not ad_id:
        return

    async with CHANNEL_PUBLISH_LOCK:
        await _delete_listing_from_channel_unlocked(context, ad_id)


async def update_listing_in_channel(context, listing, notify_guests=False):
    if not listing:
        return

    ad_id = listing.get("ad_id")
    if not ad_id:
        return

    final_listing, final_path = _resolve_channel_listing(listing)

    if final_path == "smart_inbox":
        await delete_listing_from_channel(context, ad_id)
        return

    if not final_listing:
        await delete_listing_from_channel(context, ad_id)
        return

    await publish_listing_to_channel(context, final_listing, notify_guests=notify_guests, notify_as_update=True)
