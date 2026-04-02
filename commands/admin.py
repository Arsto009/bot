import uuid
import re
import os
from datetime import datetime
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.storage import load_data, save_data
from services.keyboard import main_menu
from settings import load_config
from services.notifier import notify_subscribers
from services.channel_sync import publish_listing_to_channel
from services.channel_post_links import get_channel_post_link

# جلسات إضافة إعلان (النظام القديم)
user_states = {}
# جلسات الإضافة النصية الجديدة
text_add_sessions = {}


# =========================
# تحقق أدمن
# =========================
def is_admin(update):
    config = load_config()
    user_id = update.effective_user.id

    admin_id = config.get("ADMIN_ID")
    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        admin_id = None

    admins = config.get("ADMINS", [])
    admins = [int(a) for a in admins if str(a).isdigit()]

    return user_id == admin_id or user_id in admins


def _is_admin_id(user_id: int) -> bool:
    config = load_config()
    admin_id = config.get("ADMIN_ID")
    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        admin_id = None
    admins = config.get("ADMINS", [])
    admins = [int(a) for a in admins if str(a).isdigit()]
    return user_id == admin_id or user_id in admins


def _get_bot_username():
    cfg = load_config()
    return (os.getenv("BOT_USERNAME") or cfg.get("BOT_USERNAME") or "abo_alhassanbot").strip().lstrip("@")


def _tg_ad_link(ad_id: str):
    if not ad_id:
        return None
    bot_username = _get_bot_username()
    return f"https://t.me/{bot_username}?start=ad_{ad_id}"


# =========================
# استخراج عنوان مختصر من الكليشة
# =========================
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ARABIC_DIGITS_2 = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _norm(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = t.translate(_ARABIC_DIGITS).translate(_ARABIC_DIGITS_2)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return t


def _first_non_empty_line(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s:
            return s
    return (text or "").strip()


def _short_title_from_text(text: str) -> str:
    if not text:
        return "إعلان"

    t = _norm(text)
    tl = t.lower()

    kind = ""
    if any(w in tl for w in ["شقه", "شقة", "شقق"]):
        kind = "شقة"
    elif any(w in tl for w in ["بيت", "دار", "منزل"]):
        if "طابقين" in tl:
            kind = "بيت طابقين"
        else:
            kind = "بيت"
    elif any(w in tl for w in ["ارض", "قطعة", "قطعه"]):
        kind = "قطعة أرض"
    elif any(w in tl for w in ["محل", "محلات"]):
        kind = "محل"
    elif any(w in tl for w in ["بناية", "عمارة"]):
        kind = "بناية"

    op = ""
    if any(w in tl for w in ["للبيع", "بيع"]):
        op = "بيع"
    elif any(w in tl for w in ["للايجار", "ايجار", "اجار"]):
        op = "إيجار"

    area = ""
    m = re.search(r"(?:في\s+منطقة|منطقة)\s+([^\n\r\-—]{2,30})", t)
    if m:
        area = m.group(1).strip()

    parts = []
    if kind:
        parts.append(kind)
    if op:
        parts.append(op)
    if area:
        parts.append(area)

    if not parts:
        line = _first_non_empty_line(t)
        if len(line) > 60:
            line = line[:60] + "..."
        return line

    return " - ".join(parts)


# =========================
# حقول التقرير فقط
# =========================
def _looks_like_location_link(text: str) -> bool:
    t = (text or "").strip().lower()
    return (
        "http://" in t
        or "https://" in t
        or "maps.app" in t
        or "goo.gl" in t
        or "google.com/maps" in t
        or "maps.google" in t
    )


def _extract_report_phone(text: str) -> str:
    if not text:
        return ""

    t = _norm(text)
    digits = re.findall(r"\d", t)
    if len(digits) < 7:
        return ""

    compact = "".join(digits)

    if compact.startswith("964") and len(compact) >= 12:
        return "+" + compact
    if compact.startswith("0") and len(compact) >= 10:
        return compact

    return compact


def _looks_like_property_ad(text: str) -> bool:
    t = _norm(text)
    tl = t.lower()

    ad_keywords = [
        "للبيع", "بيع", "للايجار", "ايجار", "اجار",
        "السعر", "مساحه", "المساحة", "منطقة", "في منطقة",
        "بيت", "دار", "منزل", "شقة", "شقه", "ارض", "قطعة", "قطعه",
        "محل", "محلات", "بناية", "عمارة", "مكتب", "تجاري", "سكني"
    ]

    lines = [x.strip() for x in str(text).splitlines() if x.strip()]

    if len(text.strip()) >= 60:
        return True

    if len(lines) >= 3:
        return True

    if any(k in tl for k in ad_keywords):
        return True

    return False


def _looks_like_report_phone_only(text: str) -> bool:
    if not text:
        return False

    stripped = text.strip()

    if len(stripped) > 40:
        return False

    digits = re.findall(r"\d", _norm(stripped))
    if len(digits) < 7:
        return False

    return True


# =========================
# لوحات أزرار
# =========================
def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ إلغاء", callback_data="cancel_add")]
    ])


def media_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 تم الانتهاء", callback_data="done_media")],
        [InlineKeyboardButton("⛔ لا توجد وسائط", callback_data="no_media")]
    ])


def _textadd_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تم", callback_data="textadd_done")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="textadd_cancel")]
    ])


async def _delete_messages(context, chat_id: int, ids):
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass


async def _send_main_menu(context, chat_id: int, user_id: int):
    data = load_data()
    info = data.get("info", {})
    phones = info.get("phones", [])

    phone_list = "\n".join([f"{i+1}) {p}" for i, p in enumerate(phones)])

    text = (
        f"🏢 {info.get('business_name','')}\n\n"
        f"📍 {info.get('address','')}\n\n"
        f"📞 أرقام التواصل:\n{phone_list}\n\n"
        "اختر وسيلة التواصل أو القسم:"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=main_menu(
            data.get("categories", {}),
            phones,
            _is_admin_id(user_id),
        ),
    )


# =========================
# بدء إضافة إعلان
# =========================
async def start_add(update, context, path=None):
    if not is_admin(update):
        if update.message:
            await update.message.reply_text("❌ هذا الأمر للإدارة فقط")
        else:
            q = update.callback_query
            await q.answer()
            await q.message.reply_text("❌ هذا الأمر للإدارة فقط")
        return

    user = update.effective_user
    chat_id = (update.effective_chat.id if update.effective_chat else None)

    text_add_sessions[user.id] = {
        "path": path,
        "ads": [],
        "current": None,
        "trash": [],
        "chat_id": chat_id,
    }

    msg = (
        "✍️ أرسل الإعلانات الآن\n\n"
        "• كل نص يعتبر إعلان مستقل\n"
        "• الصور/الفيديو التي تأتي بعد النص تتبعه\n"
        "• إذا أرسلت رقم أو رابط موقع بعد الإعلان فسيُحفظ للتقرير فقط\n\n"
        "عند الانتهاء اضغط (✅ تم)"
    )

    if update.message:
        sent = await update.message.reply_text(msg, reply_markup=_textadd_keyboard())
        text_add_sessions[user.id]["trash"].append(update.message.message_id)
        text_add_sessions[user.id]["trash"].append(sent.message_id)
    else:
        q = update.callback_query
        await q.answer()
        sent = await q.message.reply_text(msg, reply_markup=_textadd_keyboard())
        text_add_sessions[user.id]["trash"].append(q.message.message_id)
        text_add_sessions[user.id]["trash"].append(sent.message_id)


# =========================
# استقبال النص
# =========================
async def handle_text(update, context):
    uid = update.effective_user.id

    # =================================================
    # النظام الجديد (إضافة إعلان نصي ذكي)
    # =================================================
    if uid in text_add_sessions:
        session = text_add_sessions[uid]
        text = (update.message.text or update.message.caption or "").strip()
        if not text:
            return

        current = session.get("current")

        if current and not _looks_like_property_ad(text):
            if _looks_like_location_link(text):
                current["report_location"] = text
                session["trash"].append(update.message.message_id)
                sent = await update.message.reply_text("📍 تم حفظ رابط الموقع للتقرير")
                session["trash"].append(sent.message_id)
                return

            if _looks_like_report_phone_only(text):
                phone = _extract_report_phone(text)
                if phone:
                    current["report_phone"] = text
                    session["trash"].append(update.message.message_id)
                    sent = await update.message.reply_text("📞 تم حفظ الرقم للتقرير")
                    session["trash"].append(sent.message_id)
                    return

        new_ad = {
            "ad_id": uuid.uuid4().hex,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "text": text,
            "photos": [],
            "videos": [],
            "documents": [],
            "media_sequence": [],
            "status": "free",
            "report_phone": "",
            "report_location": "",
            "views": 0,
            "viewers": [],
            "comments_enabled": True,
            "comments": [],
        }

        session["ads"].append(new_ad)
        session["current"] = new_ad
        session["trash"].append(update.message.message_id)

        sent = await update.message.reply_text(
            "✅ تم استلام النص.\n"
            "📸 أرسل الصور/الفيديو التابعة له.\n"
            "📞 ويمكنك إرسال رقم أو رابط موقع للتقرير فقط.\n"
            "✍️ أو أرسل نص جديد لبدء إعلان آخر.\n"
            "أو اضغط (✅ تم) للحفظ.",
        )
        session["trash"].append(sent.message_id)
        return

    # =================================================
    # النظام القديم
    # =================================================
    state = user_states.get(uid)

    if not state:
        return
    if state["step"] != "text":
        return

    state["text"] = update.message.text.strip()
    state["step"] = "media"

    await update.message.reply_text(
        "📸🎥 الآن أرسل الصور أو الفيديو الخاصة بالإعلان\n\n"
        "وعندما تنتهي اضغط (📎 تم الانتهاء)\n"
        "أو اضغط (⛔ لا توجد وسائط)",
        reply_markup=media_keyboard()
    )


# =========================
# استقبال الصور
# =========================
async def handle_photo(update, context):
    uid = update.effective_user.id

    if uid in text_add_sessions:
        session = text_add_sessions[uid]

        if not session["current"]:
            sent = await update.message.reply_text("⚠️ أرسل نص الإعلان أولاً")
            session["trash"].append(update.message.message_id)
            session["trash"].append(sent.message_id)
            return

        photo_id = update.message.photo[-1].file_id
        if photo_id not in session["current"]["photos"]:
            session["current"]["photos"].append(photo_id)
        if not any(
            m.get("type") == "photo" and m.get("file_id") == photo_id
            for m in session["current"].setdefault("media_sequence", [])
        ):
            session["current"]["media_sequence"].append({
                "type": "photo",
                "file_id": photo_id,
                "media_group_id": getattr(update.message, "media_group_id", None),
            })
        session["trash"].append(update.message.message_id)

        if len(session["current"]["photos"]) == 1 and len(session["current"]["videos"]) == 0:
            sent = await update.message.reply_text(
                "📸 تم استلام الوسائط.\n"
                "📞 يمكنك إرسال رقم أو رابط موقع للتقرير فقط.\n"
                "✍️ أرسل نص جديد لبدء إعلان آخر\n"
                "أو اضغط (✅ تم) للحفظ."
            )
            session["trash"].append(sent.message_id)
        return

    state = user_states.get(uid)
    if not state or state["step"] != "media":
        return
    photo_id = update.message.photo[-1].file_id
    if photo_id not in state["photos"]:
        state["photos"].append(photo_id)
    if not any(
        m.get("type") == "photo" and m.get("file_id") == photo_id
        for m in state.setdefault("media_sequence", [])
    ):
        state["media_sequence"].append({
            "type": "photo",
            "file_id": photo_id,
            "media_group_id": getattr(update.message, "media_group_id", None),
        })


# =========================
# استقبال الفيديو
# =========================
async def handle_video(update, context):
    uid = update.effective_user.id

    if uid in text_add_sessions:
        session = text_add_sessions[uid]

        if not session["current"]:
            sent = await update.message.reply_text("⚠️ أرسل نص الإعلان أولاً")
            session["trash"].append(update.message.message_id)
            session["trash"].append(sent.message_id)
            return

        video_id = update.message.video.file_id
        if video_id not in session["current"]["videos"]:
            session["current"]["videos"].append(video_id)
        if not any(
            m.get("type") == "video" and m.get("file_id") == video_id
            for m in session["current"].setdefault("media_sequence", [])
        ):
            session["current"]["media_sequence"].append({
                "type": "video",
                "file_id": video_id,
                "media_group_id": getattr(update.message, "media_group_id", None),
            })
        session["trash"].append(update.message.message_id)

        if len(session["current"]["videos"]) == 1 and len(session["current"]["photos"]) == 0:
            sent = await update.message.reply_text(
                "🎥 تم استلام الوسائط.\n"
                "📞 يمكنك إرسال رقم أو رابط موقع للتقرير فقط.\n"
                "✍️ أرسل نص جديد لبدء إعلان آخر\n"
                "أو اضغط (✅ تم) للحفظ."
            )
            session["trash"].append(sent.message_id)
        return

    state = user_states.get(uid)
    if not state or state["step"] != "media":
        return
    video_id = update.message.video.file_id
    if video_id not in state["videos"]:
        state["videos"].append(video_id)
    if not any(
        m.get("type") == "video" and m.get("file_id") == video_id
        for m in state.setdefault("media_sequence", [])
    ):
        state["media_sequence"].append({
            "type": "video",
            "file_id": video_id,
            "media_group_id": getattr(update.message, "media_group_id", None),
        })


# =========================
# حفظ الإعلان (قديم)
# =========================
async def save_ad(uid):
    state = user_states.get(uid)
    if not state:
        return False, None

    data = load_data()
    path = state.get("path")
    if not path:
        return False, None

    node = {"sub": data["categories"]}
    for key in path.split("/"):
        if not key:
            continue
        node = node["sub"].get(key)
        if not node:
            return False, None

    new_ad = {
        "ad_id": uuid.uuid4().hex,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "text": state["text"],
        "photos": state["photos"],
        "videos": state["videos"],
        "media_sequence": state.get("media_sequence", []),
        "status": "free",
        "report_phone": "",
        "report_location": "",
        "views": 0,
        "viewers": [],
        "comments_enabled": True,
        "comments": [],
    }

    node.setdefault("items", []).append(new_ad)

    save_data(data)
    return True, new_ad


# =========================
# أزرار الوسائط + (✅ تم) للنظام الجديد
# =========================
async def media_actions(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # =================================================
    # النظام الجديد
    # =================================================
    if uid in text_add_sessions:
        session = text_add_sessions[uid]

        if q.data == "textadd_cancel":
            chat_id = session.get("chat_id") or q.message.chat_id
            ids = list(dict.fromkeys(session.get("trash", []) + [q.message.message_id]))
            text_add_sessions.pop(uid, None)
            await _delete_messages(context, chat_id, ids)
            await _send_main_menu(context, chat_id, uid)
            return

        if q.data == "textadd_done":
            if not session["ads"]:
                sent = await q.message.reply_text("⚠️ لا يوجد إعلانات")
                session["trash"].append(sent.message_id)
                return

            data = load_data()
            path = session["path"] or ""
            chat_id = session.get("chat_id") or q.message.chat_id

            node = {"sub": data["categories"]}
            ok_path = True
            for key in path.split("/"):
                if not key:
                    continue
                node = node["sub"].get(key)
                if not node:
                    ok_path = False
                    break

            if not ok_path:
                sent = await q.message.reply_text("❌ خطأ في المسار")
                session["trash"].append(sent.message_id)
                return

            node.setdefault("items", []).extend(session["ads"])
            save_data(data)

            pending_notice = None

            if path != "smart_inbox":
                for ad in session["ads"]:
                    try:
                        await publish_listing_to_channel(context, ad, notify_guests=False)
                    except Exception:
                        pass

                try:
                    if len(session["ads"]) == 1:
                        ad = session["ads"][0]
                        title = _short_title_from_text(ad.get("text", ""))
                        pending_notice = {
                            "text": f"🆕 تم إضافة إعلان: {title}",
                            "ad_link": _tg_ad_link(ad.get("ad_id"))
                        }
                    else:
                        ads_for_notice = []
                        lines = [f"🆕 تم إضافة {len(session['ads'])} إعلانات جديدة"]
                        for i, ad in enumerate(session["ads"], start=1):
                            title_i = _short_title_from_text(ad.get("text", ""))
                            lines.append(f"{i}) {title_i}")
                            ads_for_notice.append({
                                "ad_id": ad.get("ad_id"),
                                "ad_link": _tg_ad_link(ad.get("ad_id")),
                                "post_link": get_channel_post_link(ad.get("ad_id"))
                            })
                        pending_notice = {
                            "text": "\n".join(lines),
                            "ads": ads_for_notice
                        }
                except Exception:
                    pending_notice = None

            if path == "smart_inbox":
                from commands.smart_inbox import smart_process_and_move
                _, msg = smart_process_and_move(delete_unmatched=True)

                for ad in session["ads"]:
                    try:
                        await publish_listing_to_channel(context, {"ad_id": ad.get("ad_id")}, notify_guests=False)
                    except Exception:
                        pass

                try:
                    if len(session["ads"]) == 1:
                        ad = session["ads"][0]
                        title = _short_title_from_text(ad.get("text", ""))
                        pending_notice = {
                            "text": f"🆕 تم إضافة إعلان: {title}",
                            "ad_link": _tg_ad_link(ad.get("ad_id"))
                        }
                    else:
                        ads_for_notice = []
                        lines = [f"🆕 تم إضافة {len(session['ads'])} إعلانات جديدة"]
                        for i, ad in enumerate(session["ads"], start=1):
                            title_i = _short_title_from_text(ad.get("text", ""))
                            lines.append(f"{i}) {title_i}")
                            ads_for_notice.append({
                                "ad_id": ad.get("ad_id"),
                                "ad_link": _tg_ad_link(ad.get("ad_id")),
                                "post_link": get_channel_post_link(ad.get("ad_id"))
                            })
                        pending_notice = {
                            "text": "\n".join(lines),
                            "ads": ads_for_notice
                        }
                except Exception:
                    pending_notice = None

                sent = await q.message.reply_text(msg)
                session["trash"].append(sent.message_id)

            ids = list(dict.fromkeys(session.get("trash", []) + [q.message.message_id]))
            text_add_sessions.pop(uid, None)
            await _delete_messages(context, chat_id, ids)
            await _send_main_menu(context, chat_id, uid)

            if pending_notice:
                try:
                    await notify_subscribers(
                        context,
                        pending_notice.get("text", ""),
                        ad_link=pending_notice.get("ad_link"),
                        ads=pending_notice.get("ads")
                    )
                except Exception:
                    pass
            return

    # =================================================
    # النظام القديم
    # =================================================
    if uid not in user_states:
        return

    if q.data == "done_media":
        ok, new_ad = await save_ad(uid)
        user_states.pop(uid, None)

        if ok:
            try:
                await publish_listing_to_channel(context, new_ad, notify_guests=False)
            except Exception:
                pass

            try:
                title = _short_title_from_text(new_ad.get("text", ""))
                await notify_subscribers(
                    context,
                    f"🆕 تم إضافة إعلان: {title}",
                    ad_link=_tg_ad_link(new_ad.get("ad_id"))
                )
            except Exception:
                pass

            await q.message.reply_text("✅ تم حفظ الإعلان مع الوسائط بنجاح")
        else:
            await q.message.reply_text("❌ حدث خطأ أثناء حفظ الإعلان")

    elif q.data == "no_media":
        user_states[uid]["photos"] = []
        user_states[uid]["videos"] = []

        ok, new_ad = await save_ad(uid)
        user_states.pop(uid, None)

        if ok:
            try:
                await publish_listing_to_channel(context, new_ad, notify_guests=False)
            except Exception:
                pass

            try:
                title = _short_title_from_text(new_ad.get("text", ""))
                await notify_subscribers(
                    context,
                    f"🆕 تم إضافة إعلان: {title}",
                    ad_link=_tg_ad_link(new_ad.get("ad_id"))
                )
            except Exception:
                pass

            await q.message.reply_text("✅ تم حفظ الإعلان بدون وسائط")
        else:
            await q.message.reply_text("❌ حدث خطأ أثناء الحفظ")


# =========================
# إلغاء الإضافة (قديم)
# =========================
async def cancel_add(update, context):
    q = update.callback_query
    await q.answer()

    user_states.pop(q.from_user.id, None)
    await q.message.reply_text("⛔ تم إلغاء الإضافة")


# =========================
# تسجيل الهاندلرز
# =========================
def register(app):
    app.add_handler(
        CommandHandler(
            "add",
            start_add,
            filters=filters.User(
                user_id=[load_config().get("ADMIN_ID")] + load_config().get("ADMINS", [])
            ),
        ),
        group=0,
    )

    app.add_handler(
        CallbackQueryHandler(cancel_add, pattern="^cancel_add$"),
        group=0,
    )

    app.add_handler(
        CallbackQueryHandler(
            media_actions,
            pattern="^(done_media|no_media|textadd_done|textadd_cancel)$",
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        group=1,
    )

    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo),
        group=1,
    )

    app.add_handler(
        MessageHandler(filters.VIDEO, handle_video),
        group=1,
    )
