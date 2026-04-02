from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from settings import load_config, save_config



config = load_config()

MAIN_ADMIN = config.get("ADMIN_ID")



sessions = {}





# =========================

# فلتر مخصص

# =========================

def dev_session_filter(update):

    user_id = update.effective_user.id

    return user_id in sessions





# =========================

# الكيبورد الرئيسي

# =========================

def main_keyboard(user_id):

    config = load_config()



    # إذا هو المطور الرئيسي

    if user_id == config.get("ADMIN_ID"):

        return InlineKeyboardMarkup([

            [InlineKeyboardButton("👑 تغيير المطور الرئيسي", callback_data="change_main")],

            [InlineKeyboardButton("🔐 تغيير التوكن", callback_data="change_token")],

            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")],

            [InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin")],

            [InlineKeyboardButton("🗑 حذف أدمن", callback_data="remove_admin")],

            [InlineKeyboardButton("📋 قائمة الأدمنيين", callback_data="list_admins")],

            [InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]

        ])



    # إذا مستخدم عادي دخل بكلمة السر

    else:

        return InlineKeyboardMarkup([

            [InlineKeyboardButton("👑 تغيير المطور الرئيسي", callback_data="change_main")],

            [InlineKeyboardButton("🔐 تغيير التوكن", callback_data="change_token")],

            [InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]

        ])







# =========================

# أمر /dev

# =========================

async def dev_panel(update, context):

    user_id = update.effective_user.id

    config = load_config()



    # المطور الرئيسي يدخل بدون كلمة سر

    if user_id == config.get("ADMIN_ID"):

        await update.message.reply_text(

            "🔐 لوحة تحكم المطور",

            reply_markup=main_keyboard(user_id)

        )

        sessions[user_id] = {"mode": "panel"}

        return



    # إذا ماكو كلمة سر

    if not config.get("BOT_PASSWORD"):

        await update.message.reply_text("❌ لم يتم تعيين كلمة سر بعد")

        return



    sessions[user_id] = {"mode": "check_pass"}

    await update.message.reply_text("🔐 أدخل كلمة السر:")





# =========================

# أزرار اللوحة

# =========================

async def button_handler(update, context):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass



    user_id = query.from_user.id

    config = load_config()



    if user_id not in sessions:

        return



    data = query.data



    if data == "close_panel":

        sessions.pop(user_id, None)

        await query.message.delete()

        return



    if data == "list_admins":

        admins = config.get("ADMINS", [])

        text = "📋 قائمة الأدمنيين:\n\n"



        if not admins:

            text += "لا يوجد أدمنيين"

        else:

            for a in admins:

                text += f"- {a}\n"



        await query.message.edit_text(text, reply_markup=main_keyboard(user_id))

        return



    if data == "add_admin":

        sessions[user_id]["mode"] = "add_admin"

        await query.message.edit_text("أرسل ID الأدمن الجديد:")

        return



    if data == "remove_admin":

        sessions[user_id]["mode"] = "remove_admin"

        admins = config.get("ADMINS", [])



        if not admins:

            await query.message.edit_text("لا يوجد أدمنيين للحذف", reply_markup=main_keyboard(user_id))

            return



        text = "أرسل ID الأدمن المراد حذفه:\n\n"

        for a in admins:

            text += f"- {a}\n"



        await query.message.edit_text(text)

        return



    if data == "change_pass":

        current = config.get("BOT_PASSWORD")

        sessions[user_id]["mode"] = "change_pass"



        if current:

            await query.message.edit_text(

                f"🔑 كلمة السر الحالية: {current}\n\nأرسل الجديدة:"

            )

        else:

            await query.message.edit_text("لا توجد كلمة سر حالياً. أرسل كلمة السر الجديدة:")

        return



    if data == "change_token":

        sessions[user_id]["mode"] = "change_token"

        await query.message.edit_text("أرسل التوكن الجديد:")

        return



    if data == "change_main":

        sessions[user_id]["mode"] = "change_main"

        await query.message.edit_text("أرسل ID المطور الجديد:")

        return





# =========================

# استقبال النص (فلتر مخصص)

# =========================

async def text_handler(update, context):

    user_id = update.effective_user.id



    if user_id not in sessions:

        return



    config = load_config()

    mode = sessions[user_id].get("mode")

    text = update.message.text.strip()



    if mode == "check_pass":

        if text == config.get("BOT_PASSWORD"):

            sessions[user_id] = {"mode": "panel"}

            await update.message.reply_text(

                "🔐 تم الدخول بنجاح",

                reply_markup=main_keyboard(user_id)

            )

        else:

            await update.message.reply_text("❌ كلمة السر غير صحيحة")

        return



    if mode == "add_admin":

        if not text.isdigit():

            await update.message.reply_text("❌ يجب أن يكون رقم")

            return



        config.setdefault("ADMINS", [])

        if int(text) not in config["ADMINS"]:

            config["ADMINS"].append(int(text))

            save_config(config)



        sessions[user_id] = {"mode": "panel"}

        await update.message.reply_text("✅ تم إضافة الأدمن", reply_markup=main_keyboard(user_id))

        return



    if mode == "remove_admin":

        if not text.isdigit():

            await update.message.reply_text("❌ يجب أن يكون رقم")

            return



        if int(text) in config.get("ADMINS", []):

            config["ADMINS"].remove(int(text))

            save_config(config)



        sessions[user_id] = {"mode": "panel"}

        await update.message.reply_text("✅ تم حذف الأدمن", reply_markup=main_keyboard(user_id))

        return



    if mode == "change_pass":

        config["BOT_PASSWORD"] = text

        save_config(config)

        sessions[user_id] = {"mode": "panel"}

        await update.message.reply_text("✅ تم تغيير كلمة السر", reply_markup=main_keyboard(user_id))

        return



    if mode == "change_token":

        config["BOT_TOKEN"] = text

        save_config(config)

        sessions.pop(user_id)

        await update.message.reply_text("✅ تم تغيير التوكن — أعد تشغيل البوت")

        return



    if mode == "change_main":

        if not text.isdigit():

            await update.message.reply_text("❌ يجب أن يكون رقم")

            return



        config["ADMIN_ID"] = int(text)

        save_config(config)

        sessions.pop(user_id)

        await update.message.reply_text("✅ تم تغيير المطور — أعد تشغيل البوت")

        return





# =========================

# Register

# =========================

def register(app):

    app.add_handler(CommandHandler("dev", dev_panel))



    app.add_handler(

        CallbackQueryHandler(

            button_handler,

            pattern="^(change_main|change_token|change_pass|add_admin|remove_admin|list_admins|close_panel)$"

        )

    )



    # فلتر ذكي يمنع التعارض

    app.add_handler(

        MessageHandler(

            filters.TEXT & ~filters.COMMAND,

            text_handler

        ),

        group=10

    )