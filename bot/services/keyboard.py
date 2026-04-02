from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from commands.navigation_registry import register_path





def main_menu(categories, phones, is_admin=False):

    keyboard = []



    # أزرار واتساب

    for idx, phone in enumerate(phones, start=1):

        clean = phone.replace("+", "").replace(" ", "")

        keyboard.append([

            InlineKeyboardButton(

                f"💬 واتساب {idx}",

                url=f"https://wa.me/{clean}"

            )

        ])



    # فاصل

    keyboard.append([

        InlineKeyboardButton("— الأقسام —", callback_data="ignore")

    ])



    # الأقسام الرئيسية

    for key, cat in categories.items():

        # اخفاء "المؤجر" عن غير الأدمن
        if key == "rented" and not is_admin:
            continue

        # اخفاء "فرز ذكي" عن غير الأدمن
        if key == "smart_inbox" and not is_admin:
            continue

        nav_id = register_path(key)
        keyboard.append([
            InlineKeyboardButton(
                cat["title"],
                callback_data=f"nav:{nav_id}"
            )
        ])

        if is_admin and key == "services":
            keyboard.append([
                InlineKeyboardButton(
                    "📊 عدد اعلانات الايجار",
                    callback_data="stats_rent"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    "📊 عدد اعلان البيع",
                    callback_data="stats_sale"
                )
            ])



    return InlineKeyboardMarkup(keyboard)





def sub_menu(

    path,

    node,

    is_admin=False,

    delete_mode=False,

    order_lists=False

):

    keyboard = []

    parts = path.split("/") if path else []



    # =========================

    # زر الرجوع

    # =========================

    if not delete_mode:

        if "/" in path:

            prev_path = "/".join(parts[:-1])

            nav_id = register_path(prev_path)

            keyboard.append([

                InlineKeyboardButton(

                    "⬅ رجوع",

                    callback_data=f"nav:{nav_id}"

                )

            ])

        else:

            keyboard.append([

                InlineKeyboardButton(

                    "⬅ رجوع",

                    callback_data="back:main"

                )

            ])



    has_lists = False



    # =========================

    # عرض اللستات

    # =========================

    if "sub" in node:

        for key, child in node["sub"].items():

            has_lists = True



            if order_lists:

                keyboard.append([

                    InlineKeyboardButton(

                        child["title"],

                        callback_data=f"listorder:pick:{path}/{key}"

                    )

                ])

            else:

                full_path = f"{path}/{key}" if path else key

                nav_id = register_path(full_path)

                keyboard.append([

                    InlineKeyboardButton(

                        child["title"],

                        callback_data=f"nav:{nav_id}"

                    )

                ])



    # =========================

    # أزرار الأدمن

    # =========================

    if is_admin:

        # ✅ فرز ذكي: نعرض فقط (إضافة إعلان) بدون حذف/ترتيب/نقل/تعديل
        if path == "smart_inbox" and "sub" not in node:
            keyboard.append([
                InlineKeyboardButton(
                    "➕ إضافة إعلان نصي",
                    callback_data=f"admin:add:{path}"
                )
            ])

            # زر الرجوع للرئيسية
            if not delete_mode:
                keyboard.append([
                    InlineKeyboardButton(
                        "⏮ القائمة الرئيسية",
                        callback_data="back:main"
                    )
                ])

            return InlineKeyboardMarkup(keyboard)




        # إدارة اللستات

        if has_lists:

            keyboard.append([

                InlineKeyboardButton(

                    "📂 إضافة لستة هنا",

                    callback_data=f"admin:add_list:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "🗑 حذف لستة من هذا القسم",

                    callback_data=f"admin:delete_list:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "✏️ تعديل اسم لستة",

                    callback_data=f"admin:rename_list:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "⬆⬇ ترتيب اللستات",

                    callback_data=f"listorder:start:{path}"

                )

            ])



        # إدارة الإعلانات (آخر مستوى)

        if "sub" not in node:

            keyboard.append([

                InlineKeyboardButton(

                    "➕ إضافة إعلان نصي",

                    callback_data=f"admin:add:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "🗑 إدارة الحذف",

                    callback_data=f"del:start:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "⬆⬇ ترتيب الإعلانات",

                    callback_data=f"order:start:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "✏️ تعديل إعلان",

                    callback_data=f"admin:edit_ad:{path}"

                )

            ])



            keyboard.append([

                InlineKeyboardButton(

                    "🔁 نقل إعلان",

                    callback_data=f"admin:move_ad:{path}"

                )

            ])



    # =========================

    # زر الرجوع للرئيسية

    # =========================

    if not delete_mode:

        keyboard.append([

            InlineKeyboardButton(

                "⏮ القائمة الرئيسية",

                callback_data="back:main"

            )

        ])



    return InlineKeyboardMarkup(keyboard)