from telegram.ext import (

    CommandHandler,

    MessageHandler,

    CallbackQueryHandler,

    filters

)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup



from services.storage import load_data, save_data

from commands.admin import user_states, text_add_sessions

from settings import load_config





sessions = {}  # user_id -> { mode, path, target }





# =========================

# جلب الأدمن من الإعدادات

# =========================

def get_admin_id():

    return load_config().get("ADMIN_ID")





def is_admin(update):

    config = load_config()

    user_id = update.effective_user.id

    return (

        user_id == config.get("ADMIN_ID")

        or user_id in config.get("ADMINS", [])

    )





# =========================

# أدوات

# =========================

def get_node(categories, path):

    node = {"sub": categories}

    for key in path.split("/"):

        if not key:

            continue

        node = node["sub"].get(key)

        if not node:

            return None

    return node





def cancel_keyboard():

    return InlineKeyboardMarkup([

        [InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")]

    ])





# =========================

# إضافة لستة

# =========================

async def add_list_cmd(update, context):

    if not is_admin(update):

        await update.message.reply_text("❌ هذا الأمر للإدارة فقط")

        return



    data = load_data()



    sessions[update.effective_user.id] = {

        "mode": "add",

        "path": "",

        "target": None

    }



    root = {"sub": data["categories"]}

    keyboard = []



    for key, child in root["sub"].items():

        keyboard.append([

            InlineKeyboardButton(child["title"], callback_data=f"listpick:{key}")

        ])



    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")])



    await update.message.reply_text(

        "📂 اختر القسم الذي تريد إضافة اللستة داخله:",

        reply_markup=InlineKeyboardMarkup(keyboard)

    )





# =========================

# حذف لستة

# =========================

async def delete_list_cmd(update, context):

    if not is_admin(update):

        await update.message.reply_text("❌ هذا الأمر للإدارة فقط")

        return



    data = load_data()



    sessions[update.effective_user.id] = {

        "mode": "delete",

        "path": "",

        "target": None

    }



    root = {"sub": data["categories"]}

    keyboard = []



    for key, child in root["sub"].items():

        keyboard.append([

            InlineKeyboardButton(child["title"], callback_data=f"listpick:{key}")

        ])



    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")])



    await update.message.reply_text(

        "🗑 اختر القسم الذي تريد حذف اللستة منه:",

        reply_markup=InlineKeyboardMarkup(keyboard)

    )





# =========================

# أزرار الأدمن داخل القوائم

# =========================

async def admin_list_buttons(update, context):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass



    user_id = query.from_user.id



    config = load_config()

    if user_id != config.get("ADMIN_ID") and user_id not in config.get("ADMINS", []):

       await query.message.reply_text("❌ هذا الأمر للإدارة فقط")

       return





    payload = query.data



    # إضافة لستة داخل مسار

    if payload.startswith("admin:add_list:"):

        path = payload.replace("admin:add_list:", "")

        sessions[user_id] = {"mode": "add", "path": path, "target": None}



        await query.message.reply_text(

            "✍️ أرسل اسم اللستة الجديدة الآن:",

            reply_markup=cancel_keyboard()

        )

        return



    # حذف لستة داخل مسار

    if payload.startswith("admin:delete_list:"):

        path = payload.replace("admin:delete_list:", "")

        sessions[user_id] = {"mode": "delete", "path": path, "target": None}



        data = load_data()

        node = get_node(data["categories"], path)

        keyboard = []



        if node and "sub" in node:

            for key, child in node["sub"].items():

                keyboard.append([

                    InlineKeyboardButton(

                        child["title"],

                        callback_data=f"listpick:{path}/{key}"

                    )

                ])



        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")])



        await query.message.reply_text(

            "🗑 اختر اللستة التي تريد حذفها:",

            reply_markup=InlineKeyboardMarkup(keyboard)

        )

        return



    # تعديل اسم لستة

    if payload.startswith("admin:rename_list:"):

        path = payload.replace("admin:rename_list:", "")

        sessions[user_id] = {"mode": "rename", "path": path, "target": None}



        data = load_data()

        node = get_node(data["categories"], path)

        keyboard = []



        if node and "sub" in node:

            for key, child in node["sub"].items():

                keyboard.append([

                    InlineKeyboardButton(

                        child["title"],

                        callback_data=f"listpick:{path}/{key}"

                    )

                ])



        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")])



        await query.message.reply_text(

            "✏️ اختر اللستة التي تريد تغيير اسمها:",

            reply_markup=InlineKeyboardMarkup(keyboard)

        )

        return





# =========================

# اختيار لستة

# =========================

async def pick_list(update, context):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass



    user_id = query.from_user.id

    session = sessions.get(user_id)



    if not session:

        return



    data = load_data()

    path = query.data.replace("listpick:", "")

    node = get_node(data["categories"], path)



    # لو بيها sub نكمل نزول

    if node and "sub" in node:

        keyboard = []

        for key, child in node["sub"].items():

            keyboard.append([

                InlineKeyboardButton(

                    child["title"],

                    callback_data=f"listpick:{path}/{key}"

                )

            ])



        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="listcancel")])



        await query.edit_message_text(

            "📂 اختر:",

            reply_markup=InlineKeyboardMarkup(keyboard)

        )

        return



    # تنفيذ حذف

    if session["mode"] == "delete":

        parts = path.split("/")

        parent_path = "/".join(parts[:-1])

        key = parts[-1]



        parent = get_node(data["categories"], parent_path)

        if not parent or "sub" not in parent:

            await query.edit_message_text("❌ خطأ في المسار")

            sessions.pop(user_id, None)

            return



        parent["sub"].pop(key, None)

        save_data(data)



        await query.edit_message_text("✅ تم حذف اللستة بنجاح")

        sessions.pop(user_id, None)

        return



    # تنفيذ rename

    if session["mode"] == "rename":

        session["target"] = path

        await query.edit_message_text(

            "✍️ الآن أرسل الاسم الجديد:",

            reply_markup=cancel_keyboard()

        )

        return





# =========================

# استقبال النص

# =========================

async def handle_text(update, context):

    user_id = update.effective_user.id



    # لا تمسك أثناء إضافة إعلان

    if user_id in user_states or user_id in text_add_sessions:
        return



    session = sessions.get(user_id)

    if not session:
        return



    text = update.message.text.strip()

    data = load_data()



    # إضافة

    if session["mode"] == "add":

        parent = get_node(data["categories"], session["path"])



        if not parent:

            await update.message.reply_text("❌ خطأ في المسار")

            sessions.pop(user_id, None)

            return



        parent.setdefault("sub", {})

        key = text.replace(" ", "_").lower()



        if key in parent["sub"]:

            await update.message.reply_text("⚠️ الاسم موجود بالفعل")

            return



        parent["sub"][key] = {

            "title": text,

            "items": []

        }



        save_data(data)

        await update.message.reply_text(f"✅ تم إنشاء اللستة: {text}")

        sessions.pop(user_id, None)

        return



    # تعديل اسم

    if session["mode"] == "rename":

        target = session.get("target")



        if not target:

            await update.message.reply_text("❌ لم يتم اختيار لستة")

            sessions.pop(user_id, None)

            return



        parts = target.split("/")

        parent_path = "/".join(parts[:-1])

        key = parts[-1]



        parent = get_node(data["categories"], parent_path)



        if not parent or key not in parent.get("sub", {}):

            await update.message.reply_text("❌ خطأ في المسار")

            sessions.pop(user_id, None)

            return



        parent["sub"][key]["title"] = text

        save_data(data)



        await update.message.reply_text(f"✅ تم تغيير الاسم إلى: {text}")

        sessions.pop(user_id, None)





# =========================

# إلغاء

# =========================

async def cancel(update, context):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    sessions.pop(query.from_user.id, None)

    await query.edit_message_text("❌ تم إلغاء العملية")





# =========================

# تسجيل

# =========================

def register(app):

    app.add_handler(CommandHandler("add_list", add_list_cmd))

    app.add_handler(CommandHandler("delete_list", delete_list_cmd))



    app.add_handler(CallbackQueryHandler(

        admin_list_buttons,

        pattern="^admin:(add_list|delete_list|rename_list):"

    ))



    app.add_handler(

    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),

    group=2)

    app.add_handler(CallbackQueryHandler(pick_list, pattern="^listpick:"))

    app.add_handler(CallbackQueryHandler(cancel, pattern="^listcancel$"))