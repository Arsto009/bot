import os
import uuid
import re
from telegram.ext import CommandHandler, MessageHandler, filters
from services.storage import load_data, save_data
from settings import load_config
from services.notifier import notify_subscribers
from services.channel_sync import publish_listing_to_channel
from services.channel_subscriber_notifications import notify_new_listing

UPLOAD_DIR = "uploads"
sessions = {}


# =========================
# صلاحيات الأدمن
# =========================
def is_admin(user_id):
    config = load_config()
    return (
        user_id == config.get("ADMIN_ID")
        or user_id in config.get("ADMINS", [])
    )


def _get_bot_username():
    cfg = load_config()
    return (os.getenv("BOT_USERNAME") or cfg.get("BOT_USERNAME") or "abo_alhassanbot").strip().lstrip("@")


def _tg_ad_link(ad_id: str):
    if not ad_id:
        return None
    bot_username = _get_bot_username()
    return f"https://t.me/{bot_username}?start=ad_{ad_id}"


# =========================
# أدوات التقرير فقط
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


# =========================
# جلب المسار
# =========================
def get_target_node(data, path):
    node = {"sub": data["categories"]}
    for key in path.split("/"):
        if not key:
            continue
        node = node["sub"].get(key)
        if not node:
            return None
    return node


# =========================
# بدء الإضافة
# =========================
async def start_wizard(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return

    path = context.user_data.get("add_path", "")

    sessions[user_id] = {
        "step": "text",
        "text": "",
        "photos": [],
        "videos": [],
        "documents": [],
        "media_sequence": [],
        "path": path,
        "report_phone": "",
        "report_location": "",
    }

    await update.message.reply_text("✍️ أرسل الكليشة (النص) الآن")


# =========================
# إلغاء
# =========================
async def cancel_wizard(update, context):
    user_id = update.effective_user.id

    if user_id in sessions:
        sessions.pop(user_id)
        await update.message.reply_text("🚫 تم إلغاء العملية")
    else:
        await update.message.reply_text("ℹ️ لا توجد عملية جارية")


# =========================
# استقبال النص
# =========================
async def handle_text(update, context):
    user_id = update.effective_user.id

    if user_id not in sessions:
        return

    session = sessions[user_id]
    text = (update.message.text or "").strip()

    if session["step"] == "text":
        session["text"] = text
        session["step"] = "media"
        await update.message.reply_text(
            "📸 أرسل صور / فيديو / ملفات\n"
            "وعند الانتهاء اكتب (تأكيد)\n"
            "ويمكنك قبل التأكيد إرسال رقم أو رابط موقع للتقرير فقط"
        )
        return

    if session["step"] == "media":
        phone = _extract_report_phone(text)
        if phone:
            session["report_phone"] = text
            await update.message.reply_text("📞 تم حفظ الرقم للتقرير")
            return

        if _looks_like_location_link(text):
            session["report_location"] = text
            await update.message.reply_text("📍 تم حفظ الموقع للتقرير")
            return

        if text == "تأكيد":
            data = load_data()
            node = get_target_node(data, session["path"])

            if not node:
                await update.message.reply_text("❌ خطأ في المسار")
                sessions.pop(user_id)
                return

            new_ad = {
                "ad_id": uuid.uuid4().hex,
                "text": session["text"],
                "photos": session["photos"],
                "videos": session["videos"],
                "documents": session["documents"],
                "media_sequence": session.get("media_sequence", []),
                "status": "free",
                "report_phone": session.get("report_phone", ""),
                "report_location": session.get("report_location", ""),
                "views": 0,
                "viewers": [],
                "comments_enabled": True,
                "comments": [],
            }

            node.setdefault("items", []).append(new_ad)

            save_data(data)

            try:
                await publish_listing_to_channel(context, new_ad, notify_guests=False)
            except Exception:
                pass

            if session["path"] == "smart_inbox":
                try:
                    from commands.smart_inbox import smart_process_and_move
                    smart_process_and_move(delete_unmatched=True)
                    await publish_listing_to_channel(context, {"ad_id": new_ad.get("ad_id")}, notify_guests=False)
                except Exception:
                    pass

            try:
                await notify_new_listing(context, new_ad)
            except Exception:
                pass

            sessions.pop(user_id)

            await update.message.reply_text("✅ تم حفظ الإعلان بنجاح")
        else:
            await update.message.reply_text("اكتب (تأكيد) عند الانتهاء")


# =========================
# استقبال صورة
# =========================
async def handle_photo(update, context):
    user_id = update.effective_user.id
    if user_id not in sessions:
        return

    session = sessions[user_id]
    if session["step"] != "media":
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id
    if file_id not in session["photos"]:
        session["photos"].append(file_id)
    if not any(
        m.get("type") == "photo" and m.get("file_id") == file_id
        for m in session.setdefault("media_sequence", [])
    ):
        session["media_sequence"].append({
            "type": "photo",
            "file_id": file_id,
            "media_group_id": getattr(update.message, "media_group_id", None),
        })

    await update.message.reply_text(
        f"🖼 تم حفظ الصورة ({len(session['photos'])})"
    )


# =========================
# استقبال فيديو
# =========================
async def handle_video(update, context):
    user_id = update.effective_user.id
    if user_id not in sessions:
        return

    session = sessions[user_id]
    if session["step"] != "media":
        return

    video = update.message.video
    if video.file_id not in session["videos"]:
        session["videos"].append(video.file_id)
    if not any(
        m.get("type") == "video" and m.get("file_id") == video.file_id
        for m in session.setdefault("media_sequence", [])
    ):
        session["media_sequence"].append({
            "type": "video",
            "file_id": video.file_id,
            "media_group_id": getattr(update.message, "media_group_id", None),
        })

    await update.message.reply_text(
        f"🎥 تم حفظ الفيديو ({len(session['videos'])})"
    )


# =========================
# استقبال ملف (صورة أو فيديو)
# =========================
async def handle_document(update, context):
    user_id = update.effective_user.id
    if user_id not in sessions:
        return

    session = sessions[user_id]
    if session["step"] != "media":
        return

    document = update.message.document
    file_id = document.file_id

    if document.mime_type.startswith("image"):
        if file_id not in session["photos"]:
            session["photos"].append(file_id)
        if not any(
            m.get("type") == "photo" and m.get("file_id") == file_id
            for m in session.setdefault("media_sequence", [])
        ):
            session["media_sequence"].append({
                "type": "photo",
                "file_id": file_id,
                "media_group_id": getattr(update.message, "media_group_id", None),
            })
        await update.message.reply_text(
            f"🖼 تم حفظ الصورة ({len(session['photos'])})"
        )

    elif document.mime_type.startswith("video"):
        if file_id not in session["videos"]:
            session["videos"].append(file_id)
        if not any(
            m.get("type") == "video" and m.get("file_id") == file_id
            for m in session.setdefault("media_sequence", [])
        ):
            session["media_sequence"].append({
                "type": "video",
                "file_id": file_id,
                "media_group_id": getattr(update.message, "media_group_id", None),
            })
        await update.message.reply_text(
            f"🎥 تم حفظ الفيديو ({len(session['videos'])})"
        )
    else:
        session["documents"].append(file_id)
        await update.message.reply_text(
            f"📎 تم حفظ الملف ({len(session['documents'])})"
        )


# =========================
# Register
# =========================
def register(app):

    app.add_handler(CommandHandler("add_listing", start_wizard))
    app.add_handler(CommandHandler("cancel", cancel_wizard))

    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo),
        group=3
    )

    app.add_handler(
        MessageHandler(filters.VIDEO, handle_video),
        group=3
    )

    app.add_handler(
        MessageHandler(filters.Document.ALL, handle_document),
        group=3
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        group=3
    )
