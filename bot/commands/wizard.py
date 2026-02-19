import os
import uuid
from telegram.ext import CommandHandler, MessageHandler, filters
from services.storage import load_data, save_data
from settings import load_config

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
        "path": path
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

    if session["step"] == "text":
        session["text"] = update.message.text
        session["step"] = "media"
        await update.message.reply_text(
            "📸 أرسل صور / فيديو / ملفات\n"
            "وعند الانتهاء اكتب (تأكيد)"
        )
        return

    if session["step"] == "media":
        if update.message.text.strip() == "تأكيد":

            data = load_data()
            node = get_target_node(data, session["path"])

            if not node:
                await update.message.reply_text("❌ خطأ في المسار")
                sessions.pop(user_id)
                return

            node.setdefault("items", []).append({
                "text": session["text"],
                "photos": session["photos"],
                "videos": session["videos"],
                "documents": session["documents"]
            })

            save_data(data)
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
    session["photos"].append(file_id)

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
    session["videos"].append(video.file_id)

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
        session["photos"].append(file_id)
        await update.message.reply_text(
            f"🖼 تم حفظ الصورة ({len(session['photos'])})"
        )

    elif document.mime_type.startswith("video"):
        session["videos"].append(file_id)
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