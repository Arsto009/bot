from telegram.ext import CallbackQueryHandler

from telegram import (

    InlineKeyboardButton,

    InlineKeyboardMarkup,

    InputMediaPhoto,

    InputMediaVideo

)

from telegram.error import BadRequest



from services.storage import load_data, save_data

from services.keyboard import main_menu, sub_menu

from commands.admin import start_add

from settings import load_config

from commands.menu_extra import get_extra_keyboard

from commands.shared_ads import ad_message_map, get_node

from commands.navigation_registry import get_path





config = load_config()

ADMIN_ID = config.get("ADMIN_ID")





menu_message_id = {}

delete_states = {}

order_states = {}

list_order_states = {}

user_pages = {}





# =====================================================

# أدوات مساعدة

# =====================================================



def parent_path(path):

    parts = path.split("/")

    if len(parts) >= 2:

        return "/".join(parts[:-1])

    return ""





def is_leaf(node):

    # تعتبر لستة إذا بيها items

    return isinstance(node.get("items"), list)



async def clear_page(context, chat_id, user_id):

    for msg_id in user_pages.get(user_id, []):

        try:

            await context.bot.delete_message(chat_id, msg_id)

        except:

            pass

    user_pages[user_id] = []





async def safe_edit(context, chat_id, msg_id, text, keyboard):

    try:

        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=msg_id,

            text=text,

            reply_markup=keyboard

        )

    except BadRequest:

        pass





# =====================================================

# ترتيب الإعلانات

# =====================================================



def move_item(path, idx, direction):

    data = load_data()

    node = get_node(data["categories"], path)

    if not node:

        return



    items = node.get("items", [])



    if direction == "up" and idx > 0:

        items[idx - 1], items[idx] = items[idx], items[idx - 1]

    elif direction == "down" and idx < len(items) - 1:

        items[idx + 1], items[idx] = items[idx], items[idx + 1]



    save_data(data)





# =====================================================

# ترتيب اللستات

# =====================================================



def move_list(path, key, direction):

    data = load_data()

    parent = get_node(data["categories"], path)



    if not parent or "sub" not in parent:

        return



    keys = list(parent["sub"].keys())



    if key not in keys:

        return



    idx = keys.index(key)



    if direction == "up" and idx > 0:

        keys[idx - 1], keys[idx] = keys[idx], keys[idx - 1]

    elif direction == "down" and idx < len(keys) - 1:

        keys[idx + 1], keys[idx] = keys[idx], keys[idx + 1]



    new_sub = {}

    for k in keys:

        new_sub[k] = parent["sub"][k]



    parent["sub"] = new_sub

    save_data(data)





# =====================================================

# عرض الإعلانات

# =====================================================



async def render_ads(context, query, path, admin):

    chat_id = query.message.chat_id

    user_id = query.from_user.id

    # إعادة تعيين الأدراج عند فتح الصفحة
    from commands.menu_extra import drawer_states
    drawer_states.clear()


    data = load_data()

    node = get_node(data["categories"], path)



    if not node:

        return



    items = node.get("items", [])



    # اخفاء الصفحة السابقة

    await clear_page(context, chat_id, user_id)



    delete_state = delete_states.get(user_id, {})

    order_mode = order_states.get(user_id, False)

    selected = delete_state.get("selected", set())



    # =========================

    # الشريط العلوي

    # =========================



    if order_mode:

        top_kb = InlineKeyboardMarkup([

            [InlineKeyboardButton("✅ تم", callback_data=f"order:done:{path}")],

            [InlineKeyboardButton("❌ إلغاء", callback_data=f"order:cancel:{path}")]

        ])

        title = "⬆⬇ وضع ترتيب الإعلانات"



    elif delete_state.get("active"):

        top_kb = InlineKeyboardMarkup([

            [

                InlineKeyboardButton("☑ اختيار الكل", callback_data=f"del:all:{path}"),

                InlineKeyboardButton("🗑 حذف المحدد", callback_data=f"del:do:{path}")

            ],

            [

                InlineKeyboardButton("❌ إلغاء", callback_data=f"del:cancel:{path}")

            ]

        ])

        title = "🧹 إدارة الحذف"



    else:

        if admin:

            top_kb = InlineKeyboardMarkup([

                [InlineKeyboardButton("➕ إضافة إعلان هنا", callback_data=f"admin:add:{path}")],

                [InlineKeyboardButton("🗑 إدارة الحذف", callback_data=f"del:start:{path}")],

                [InlineKeyboardButton("⬆⬇ ترتيب الإعلانات", callback_data=f"order:start:{path}")],

                [InlineKeyboardButton("⬅ رجوع", callback_data=f"adsback:{path}")]

            ])

            title = "📋 إدارة الإعلانات"

        else:

            top_kb = InlineKeyboardMarkup([

                [InlineKeyboardButton("⬅ رجوع", callback_data=f"adsback:{path}")]

            ])

            title = "📋 الإعلانات"



    # ارسال الشريط العلوي

    top_msg = await query.message.reply_text(title, reply_markup=top_kb)

    user_pages.setdefault(user_id, []).append(top_msg.message_id)



    # =========================

    # عرض كل إعلان

    # =========================



    for idx, item in enumerate(items):



        text = f"#{idx+1}\n{item.get('text', '')}"



        # اختيار نوع الكيبورد

        if delete_state.get("active"):

            is_selected = idx in selected

            label = "☑ محدد" if is_selected else "⬜ تحديد"

            kb = InlineKeyboardMarkup([

                [InlineKeyboardButton(label, callback_data=f"del:toggle:{path}:{idx}")]

            ])



        elif order_mode:

            kb = InlineKeyboardMarkup([

                [

                    InlineKeyboardButton("⬆ رفع", callback_data=f"order:up:{path}:{idx}"),

                    InlineKeyboardButton("⬇ تنزيل", callback_data=f"order:down:{path}:{idx}")

                ]

            ])



        else:

            kb = get_extra_keyboard(path, idx, admin, user_id) if admin else None



        # ارسال النص

        msg = await query.message.reply_text(text, reply_markup=kb)



        # تسجيل الرسالة للتحديث لاحقاً

        ad_message_map.setdefault(path, {}).setdefault(idx, []).append(

            (msg.chat_id, msg.message_id, user_id)

        )



        user_pages[user_id].append(msg.message_id)



        # ===== عرض الصور =====

        photos = item.get("photos", [])

        if photos:

            try:

                media = [InputMediaPhoto(p) for p in photos[:10]]

                msgs = await query.message.reply_media_group(media)



                for mm in msgs:

                    user_pages.setdefault(user_id, []).append(mm.message_id)

 

            except:

                pass





        # ===== عرض الفيديو =====

        videos = item.get("videos", [])

        if videos:

            for v in videos:

                try:

                    mv = await query.message.reply_video(v)

                    user_pages[user_id].append(mv.message_id)

                except:

                    pass





        # ===== عرض الملفات =====

        documents = item.get("documents", [])

        if documents:

           for d in documents:

               md = await query.message.reply_document(d)

               user_pages[user_id].append(md.message_id)



    # =========================

    # نهاية الإعلانات

    # =========================



    bottom = await query.message.reply_text(

        "⬅ نهاية الإعلانات",

        reply_markup=InlineKeyboardMarkup([

            [InlineKeyboardButton("⬅ رجوع", callback_data=f"adsback:{path}")]

        ])

    )



    user_pages[user_id].append(bottom.message_id)







# =====================================================

# الهاندلر الرئيسي

# =====================================================



async def handle_menu(update, context):

    query = update.callback_query

    await query.answer()



    data = load_data()

    categories = data["categories"]

    phones = data["info"]["phones"]



    user_id = query.from_user.id

    config = load_config()

    admin = (user_id == config.get("ADMIN_ID") or user_id in config.get("ADMINS", []))

    payload = query.data

    chat_id = query.message.chat_id



    # =========================

    # رجوع من الإعلانات

    # =========================



    if payload.startswith("adsback:"):

        path = payload.replace("adsback:", "")

        delete_states.pop(user_id, None)

        order_states.pop(user_id, None)



        await clear_page(context, chat_id, user_id)

        ad_message_map[path] = {}



        parent = parent_path(path)

        node = get_node(categories, parent)



        await safe_edit(

            context,

            chat_id,

            query.message.message_id,

            "اختر من القائمة:",

            sub_menu(parent, node, admin)

        )

        return



    # =========================

    # إدارة الحذف

    # =========================



    if payload.startswith("del:"):

        parts = payload.split(":")

        action = parts[1]

        path = parts[2]



        state = delete_states.setdefault(user_id, {

            "active": False,

            "selected": set()

        })



        if action == "start":

            state["active"] = True

            state["selected"] = set()

            await render_ads(context, query, path, admin)

            return



        if action == "toggle":

            idx = int(parts[3])

            if idx in state["selected"]:

                state["selected"].remove(idx)

            else:

                state["selected"].add(idx)

            await render_ads(context, query, path, admin)

            return



        if action == "all":

            node = get_node(categories, path)

            state["selected"] = set(range(len(node.get("items", []))))

            await render_ads(context, query, path, admin)

            return



        if action == "do":

            node = get_node(categories, path)

            node["items"] = [

                item for i, item in enumerate(node.get("items", []))

                if i not in state["selected"]

            ]

            save_data(data)

            delete_states.pop(user_id, None)

            await render_ads(context, query, path, admin)

            return



        if action == "cancel":

            delete_states.pop(user_id, None)

            await render_ads(context, query, path, admin)

            return



    # =========================

    # ترتيب الإعلانات

    # =========================



    if payload.startswith("order:start:"):

        path = payload.replace("order:start:", "")

        order_states[user_id] = True

        await render_ads(context, query, path, admin)

        return



    if payload.startswith("order:up:") or payload.startswith("order:down:"):

        parts = payload.split(":")

        direction = parts[1]

        path = parts[2]

        idx = int(parts[3])

        move_item(path, idx, direction)

        await render_ads(context, query, path, admin)

        return



    if payload.startswith("order:done:"):

        order_states.pop(user_id, None)

        await render_ads(context, query, payload.replace("order:done:", ""), admin)

        return



    if payload.startswith("order:cancel:"):

        order_states.pop(user_id, None)

        await render_ads(context, query, payload.replace("order:cancel:", ""), admin)

        return



    # =========================

    # ترتيب اللستات

    # =========================



    if payload.startswith("listorder:start:"):

        path = payload.replace("listorder:start:", "")

        node = get_node(categories, path)



        await safe_edit(

            context,

            chat_id,

            query.message.message_id,

            "⬆⬇ اختر لستة لترتيبها:",

            sub_menu(path, node, admin, order_lists=True)

        )

        return



    if payload.startswith("listorder:pick:"):

        full = payload.replace("listorder:pick:", "")

        parent = parent_path(full)

        key = full.split("/")[-1]



        kb = InlineKeyboardMarkup([

            [

                InlineKeyboardButton("⬆ رفع", callback_data=f"listorder:up:{parent}:{key}"),

                InlineKeyboardButton("⬇ تنزيل", callback_data=f"listorder:down:{parent}:{key}")

            ],

            [

                InlineKeyboardButton("❌ إنهاء", callback_data=f"listorder:cancel:{parent}")

            ]

        ])



        await query.message.reply_text(f"📂 ترتيب: {key}", reply_markup=kb)

        return



    if payload.startswith("listorder:up:") or payload.startswith("listorder:down:"):

        parts = payload.split(":")

        direction = parts[1]

        path = parts[2]

        key = parts[3]

        move_list(path, key, direction)



        node = get_node(categories, path)



        await safe_edit(

            context,

            chat_id,

            query.message.message_id,

            "⬆⬇ ترتيب اللستات:",

            sub_menu(path, node, admin, order_lists=True)

        )

        return



    if payload.startswith("listorder:cancel:"):

        path = payload.replace("listorder:cancel:", "")

        node = get_node(categories, path)



        await safe_edit(

            context,

            chat_id,

            query.message.message_id,

            "اختر من القائمة:",

            sub_menu(path, node, admin)

        )

        return



    # =========================

    # إضافة إعلان

    # =========================



    if payload.startswith("admin:add:"):

        path = payload.replace("admin:add:", "")

        await clear_page(context, chat_id, user_id)

        await start_add(update, context, path)

        return



    # =========================

    # الرئيسية

    # =========================



    if payload == "back:main":

        await safe_edit(

            context,

            chat_id,

            query.message.message_id,

            f"🏢 {data['info']['business_name']}\n\n"

            f"📍 {data['info']['address']}\n\n"

            f"📞 أرقام التواصل:\n" +

            "\n".join(data["info"]["phones"]) +

            "\n\nاختر وسيلة التواصل أو القسم:",

            main_menu(categories, phones, admin)

        )

        return



    # =========================

    # تنقل (nav system)

    # =========================



    if payload.startswith("nav:"):

        nav_id = payload.replace("nav:", "")

        path = get_path(nav_id)



        if not path:

            return



        node = get_node(categories, path)



        if not node:

            return



        # إذا يحتوي لستات فرعية → اعرض اللستات

        if node.get("sub"):

            await safe_edit(

                context,

                chat_id,

                query.message.message_id,

                "اختر من القائمة:",

                sub_menu(path, node, admin)

            )

            return



        # إذا ما يحتوي sub → هذا مستوى الكلايش

        await render_ads(context, query, path, admin)

        return













def register(app):

    app.add_handler(

        CallbackQueryHandler(handle_menu)

    )








