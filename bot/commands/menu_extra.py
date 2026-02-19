from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from services.storage import load_data, save_data
from settings import load_config
from commands.shared_ads import ad_message_map, get_node

config = load_config()
ADMIN_ID = config.get("ADMIN_ID")

# جلسات التعديل
edit_sessions = {}


# =====================================================
# الكيبورد الإضافي تحت الإعلان
# =====================================================

def get_extra_keyboard(path, idx, admin):

    data = load_data()
    node = get_node(data["categories"], path)

    if not node:
        return None

    items = node.get("items", [])
    if idx >= len(items):
        return None

    item = items[idx]
    status = item.get("status", "free")

    free_label = "☑ غير مؤجر" if status == "free" else "⬜ غير مؤجر"
    rented_label = "☑ مؤجر" if status == "rented" else "⬜ مؤجر"

    if admin:
        keyboard = [
            [
                InlineKeyboardButton(
                    free_label,
                    callback_data=f"status:free:{path}:{idx}"
                ),
                InlineKeyboardButton(
                    rented_label,
                    callback_data=f"status:rented:{path}:{idx}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ تعديل إعلان",
                    callback_data=f"edit:{path}:{idx}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف الإعلان",
                    callback_data=f"quickdel:{path}:{idx}"
                )
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(free_label, callback_data="ignore"),
                InlineKeyboardButton(rented_label, callback_data="ignore")
            ]
        ]

    return InlineKeyboardMarkup(keyboard)


# =====================================================
# تحديث مباشر عند جميع المستخدمين
# =====================================================

def is_admin_user(user_id):
    config = load_config()
    return (
        user_id == config.get("ADMIN_ID")
        or user_id in config.get("ADMINS", [])
    )


async def refresh_everywhere(context, path, idx):

    data = load_data()
    node = get_node(data["categories"], path)
    items = node.get("items", [])

    if idx >= len(items):
        return

    text = f"#{idx+1}\n{items[idx].get('text','')}"

    targets = ad_message_map.get(path, {}).get(idx, [])

    config = load_config()
    ADMIN_ID = config.get("ADMIN_ID")
    ADMINS = config.get("ADMINS", [])

    for chat_id, message_id, owner_id in targets:
        try:
            is_admin = (
                owner_id == ADMIN_ID
                or owner_id in ADMINS
            )

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=get_extra_keyboard(
                    path,
                    idx,
                    is_admin
                ) if is_admin else None
            )

        except:
            pass




# =====================================================
# الهاندلر الرئيسي
# =====================================================

async def handle_extra(update, context):

    query = update.callback_query
    data_cb = query.data
    user_id = query.from_user.id

    await query.answer()

    # تجاهل ضغط الضيف
    if data_cb == "ignore":
        return

    # =========================
    # تغيير الحالة
    # =========================
    if data_cb.startswith("status:"):

        config = load_config()
        if user_id != config.get("ADMIN_ID") and user_id not in config.get("ADMINS", []):
             return


        parts = data_cb.split(":")
        status = parts[1]
        path = parts[2]
        idx = int(parts[3])

        data = load_data()
        node = get_node(data["categories"], path)

        if not node:
            return

        node["items"][idx]["status"] = status
        save_data(data)

        await refresh_everywhere(context, path, idx)
        return
    # =========================
    # حذف سريع للإعلان
    # =========================
    if data_cb.startswith("quickdel:"):

        config = load_config()
        if user_id != config.get("ADMIN_ID") and user_id not in config.get("ADMINS", []):
            return

        parts = data_cb.split(":")
        path = parts[1]
        idx = int(parts[2])

        data = load_data()
        node = get_node(data["categories"], path)

        if not node:
            return

        items = node.get("items", [])

        if idx >= len(items):
            return

        # حذف الإعلان
        items.pop(idx)
        save_data(data)

        await query.message.reply_text("✅ تم حذف الإعلان بالكامل")

        # إعادة تحديث الصفحة
        from commands.menu import render_ads
        await render_ads(context, update.callback_query, path, True)

        return

    # =========================
    # بدء تعديل إعلان
    # =========================
    if data_cb.startswith("edit:"):

        config = load_config()
        if user_id != config.get("ADMIN_ID") and user_id not in config.get("ADMINS", []):
         return


        parts = data_cb.split(":")
        path = parts[1]
        idx = int(parts[2])

        edit_sessions[user_id] = {
            "path": path,
            "idx": idx,
            "step": "text"
        }

        await query.message.reply_text(
            "✍️ اكتب النص الجديد للإعلان:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء", callback_data="editcancel")]
            ])
        )
        return

    # =========================
    # إلغاء التعديل
    # =========================
    if data_cb == "editcancel":
        edit_sessions.pop(user_id, None)
        await query.message.reply_text("❌ تم إلغاء العملية")
        return


# =====================================================
# استقبال النص الجديد
# =====================================================

async def handle_edit_text(update, context):

    user_id = update.effective_user.id

    if user_id not in edit_sessions:
        return

    session = edit_sessions[user_id]

    if session["step"] != "text":
        return

    new_text = update.message.text

    data = load_data()
    node = get_node(data["categories"], session["path"])

    if not node:
        return

    node["items"][session["idx"]]["text"] = new_text
    save_data(data)

    session["step"] = "photos"

    await update.message.reply_text(
        "هل تريد تعديل الصور؟",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("نعم", callback_data="editphotos:yes"),
                InlineKeyboardButton("لا", callback_data="editphotos:no")
            ]
        ])
    )


# =====================================================
# التعامل مع خيار الصور
# =====================================================

async def handle_edit_photos(update, context):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in edit_sessions:
        return

    session = edit_sessions[user_id]

    if query.data == "editphotos:no":

        await refresh_everywhere(context, session["path"], session["idx"])
        edit_sessions.pop(user_id, None)
        await query.message.reply_text("✅ تم التحديث بنجاح")
        return

    if query.data == "editphotos:yes":

        session["step"] = "new_photos"
        session["photos"] = []

        await query.message.reply_text(
            "📸 أرسل الصور الجديدة ثم اضغط (تم)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تم", callback_data="editphotos:done")]
            ])
        )
        return

    if query.data == "editphotos:done":

        data = load_data()
        node = get_node(data["categories"], session["path"])

        if not node:
            return

        node["items"][session["idx"]]["photos"] = session.get("photos", [])
        save_data(data)

        await refresh_everywhere(context, session["path"], session["idx"])

        edit_sessions.pop(user_id, None)
        await query.message.reply_text("✅ تم تحديث الصور")
        return


# =====================================================
# استقبال الصور الجديدة
# =====================================================

async def handle_new_photos(update, context):

    user_id = update.effective_user.id

    if user_id not in edit_sessions:
        return

    session = edit_sessions[user_id]

    if session["step"] != "new_photos":
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()

    session.setdefault("photos", []).append(file.file_id)

    await update.message.reply_text("📷 تم حفظ الصورة")


# =====================================================
# تسجيل الهاندلرات
# =====================================================

def register(app):

    app.add_handler(
        CallbackQueryHandler(
            handle_extra,
            pattern="^(status:|edit:|editcancel|ignore|quickdel:)"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            handle_edit_photos,
            pattern="^editphotos:"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_edit_text
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_new_photos
        )
    )