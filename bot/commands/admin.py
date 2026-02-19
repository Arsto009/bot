from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.storage import load_data, save_data
from settings import load_config

# جلسات إضافة إعلان
user_states = {}
# جلسات الإضافة النصية الجديدة
text_add_sessions = {}


# =========================
# تحقق أدمن
# =========================
def is_admin(update):
    config = load_config()
    user_id = update.effective_user.id
    return (
        user_id == config.get("ADMIN_ID")
        or user_id in config.get("ADMINS", [])
    )



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

    text_add_sessions[user.id] = {
        "path": path,
        "ads": [],
        "current": None
    }

    msg = (
        "✍️ أرسل الإعلانات الآن\n\n"
        "• كل نص يعتبر إعلان مستقل\n"
        "• الصور والفيديو التي تأتي بعد النص تتبع له\n\n"
        "عند الانتهاء اضغط (✅ تم)"
    )

    if update.message:
        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تم", callback_data="textadd_done")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="textadd_cancel")]
            ])
        )
    else:
        q = update.callback_query
        await q.answer()
        await q.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تم", callback_data="textadd_done")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="textadd_cancel")]
            ])
        )


# =========================
# استقبال النص
# =========================
async def handle_text(update, context):
    uid = update.effective_user.id
    # =================================================
    # 🆕 النظام الجديد (إضافة إعلان نصي ذكي)
    # =================================================
    if uid in text_add_sessions:

        session = text_add_sessions[uid]
        text = (update.message.text or update.message.caption or "").strip()

        if not text:
            return

        new_ad = {
            "text": text,
            "photos": [],
            "videos": [],
            "status": "free"
        }

        session["ads"].append(new_ad)
        session["current"] = new_ad

        await update.message.reply_text(            "✅ تم استلام النص.\n"            "📸 أرسل الصور أو الفيديو التابعة له.\n"            "✍️ أو أرسل نص جديد لبدء إعلان آخر.\n"            "أو اضغط (✅ تم) للحفظ."        )
        return   # ⚠️ مهم جداً حتى لا يكمل للكود القديم

    state = user_states.get(uid)

    # لا تتدخل إذا ماكو جلسة إضافة
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
    # =================================================
    # 🆕 النظام الجديد (إضافة إعلان نصي ذكي)
    # =================================================
    if uid in text_add_sessions:        session = text_add_sessions[uid]        # إذا ماكو نص سابق        if not session["current"]:            await update.message.reply_text("⚠️ أرسل نص الإعلان أولاً")            return        photo_id = update.message.photo[-1].file_id        session["current"]["photos"].append(photo_id)        # أرسل رسالة واحدة فقط عند أول وسائط        if (            len(session["current"]["photos"]) == 1            and len(session["current"]["videos"]) == 0        ):            await update.message.reply_text(                "📸 تم استلام الوسائط.\n"                "✍️ أرسل نص جديد لبدء إعلان آخر\n"                "أو اضغط (✅ تم) للحفظ."            )        return  # مهم جداً حتى لا يكمل للنظام القديم    state = user_states.get(uid)    if not state or state["step"] != "media":        return    state["photos"].append(update.message.photo[-1].file_id)

# =========================
# استقبال الفيديو
# =========================
async def handle_video(update, context):
    uid = update.effective_user.id
    # =================================================
    # 🆕 النظام الجديد (إضافة إعلان نصي ذكي)
    # =================================================
    if uid in text_add_sessions:        session = text_add_sessions[uid]        # إذا ماكو نص سابق        if not session["current"]:            await update.message.reply_text("⚠️ أرسل نص الإعلان أولاً")            return        video_id = update.message.video.file_id        session["current"]["videos"].append(video_id)        # أرسل رسالة واحدة فقط عند أول وسائط        if (            len(session["current"]["videos"]) == 1            and len(session["current"]["photos"]) == 0        ):            await update.message.reply_text(                "🎥 تم استلام الوسائط.\n"                "✍️ أرسل نص جديد لبدء إعلان آخر\n"                "أو اضغط (✅ تم) للحفظ."            )        return  # مهم جداً حتى لا يكمل للنظام القديم    state = user_states.get(uid)    if not state or state["step"] != "media":        return    state["videos"].append(update.message.video.file_id)

# =========================
# حفظ الإعلان
# =========================
async def save_ad(uid):
    state = user_states.get(uid)
    if not state:
        return False

    data = load_data()
    path = state.get("path")

    if not path:
        return False

    # الوصول للعقدة الصحيحة
    node = {"sub": data["categories"]}

    for key in path.split("/"):
        if not key:
            continue
        node = node["sub"].get(key)
        if not node:
            return False

    node.setdefault("items", []).append({
        "text": state["text"],
        "photos": state["photos"],
        "videos": state["videos"]
    })

    save_data(data)
    return True


# =========================
# أزرار الوسائط
# =========================
async def media_actions(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    # =================================================
    # 🆕 النظام الجديد (إضافة إعلان نصي ذكي)
    # =================================================
    if uid in text_add_sessions:

        session = text_add_sessions[uid]

        # إلغاء
        if q.data == "textadd_cancel":
            text_add_sessions.pop(uid, None)
            await q.message.reply_text("❌ تم إلغاء العملية")
            return

        # حفظ
        if q.data == "textadd_done":

            if not session["ads"]:
                await q.message.reply_text("⚠️ لا يوجد إعلانات لحفظها")
                return

            data = load_data()
            path = session["path"]

            node = {"sub": data["categories"]}

            for key in path.split("/"):
                if not key:
                    continue
                node = node["sub"].get(key)
                if not node:
                    await q.message.reply_text("❌ خطأ في المسار")
                    return

            node.setdefault("items", []).extend(session["ads"])
            save_data(data)

            text_add_sessions.pop(uid, None)

            await q.message.reply_text("✅ تم حفظ جميع الإعلانات بنجاح")
            return
    if uid not in user_states:
        return

    if q.data == "done_media":
        ok = await save_ad(uid)
        user_states.pop(uid, None)

        if ok:
            await q.message.reply_text("✅ تم حفظ الإعلان مع الوسائط بنجاح")
        else:
            await q.message.reply_text("❌ حدث خطأ أثناء حفظ الإعلان")

    elif q.data == "no_media":
        user_states[uid]["photos"] = []
        user_states[uid]["videos"] = []

        ok = await save_ad(uid)
        user_states.pop(uid, None)

        if ok:
            await q.message.reply_text("✅ تم حفظ الإعلان بدون وسائط")
        else:
            await q.message.reply_text("❌ حدث خطأ أثناء الحفظ")


# =========================
# إلغاء الإضافة
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
        CommandHandler("add", lambda u, c: start_add(u, c)),
        group=0
    )

    app.add_handler(
        CallbackQueryHandler(cancel_add, pattern="^cancel_add$"),
        group=0
    )

    app.add_handler(
        CallbackQueryHandler(
            media_actions,
            pattern="^(done_media|no_media|textadd_done|textadd_cancel)$"
        ),
        group=0
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        group=1
    )

    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo),
        group=1
    )

    app.add_handler(
        MessageHandler(filters.VIDEO, handle_video),
        group=1
    )