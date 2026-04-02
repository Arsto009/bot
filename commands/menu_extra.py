import os
import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, CommandHandler

from services.storage import load_data, save_data
from settings import load_config, save_config
from services.notifier import notify_subscribers
from services.channel_sync import publish_listing_to_channel, delete_listing_from_channel, update_listing_in_channel

from commands.shared_ads import ad_message_map, get_node
from commands.navigation_registry import register_path, get_path


# جلسات التعديل
edit_sessions = {}
drawer_states = {}
move_sessions = {}
comment_sessions = {}

# تتبع رسائل عرض التعليقات لكل مستخدم/إعلان
open_comment_views = {}

# تتبع رسالة "اكتب تعليقك الآن"
comment_prompt_messages = {}


def _get_bot_username():
    cfg = load_config()
    return (os.getenv("BOT_USERNAME") or cfg.get("BOT_USERNAME") or "abo_alhassanbot").strip().lstrip("@")


def _tg_ad_link(ad_id: str):
    if not ad_id:
        return None
    bot_username = _get_bot_username()
    return f"https://t.me/{bot_username}?start=ad_{ad_id}"


# =====================================================
# استخراج عنوان مختصر من الكليشة
# =====================================================
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


# =====================================================
# إعداد عام للتعليقات
# =====================================================

def comments_globally_enabled():
    cfg = load_config()
    return bool(cfg.get("COMMENTS_GLOBALLY_ENABLED", True))


async def open_comments_all_cmd(update, context):
    user_id = update.effective_user.id
    if not is_admin_user(user_id):
        await update.message.reply_text("❌ هذا الأمر للإدارة فقط.")
        return

    cfg = load_config()
    cfg["COMMENTS_GLOBALLY_ENABLED"] = True
    save_config(cfg)

    await update.message.reply_text("✅ تم فتح التعليقات على كل الإعلانات.")


async def close_comments_all_cmd(update, context):
    user_id = update.effective_user.id
    if not is_admin_user(user_id):
        await update.message.reply_text("❌ هذا الأمر للإدارة فقط.")
        return

    cfg = load_config()
    cfg["COMMENTS_GLOBALLY_ENABLED"] = False
    save_config(cfg)

    await update.message.reply_text("✅ تم غلق التعليقات على كل الإعلانات.")


# =====================================================
# مزامنة نسخة المؤجر (حسب ad_id)
# =====================================================

def sync_rented_item(
    data,
    ad_id,
    *,
    text=None,
    photos=None,
    videos=None,
    documents=None,
    origin_path=None,
    report_phone=None,
    report_location=None,
    comments_enabled=None,
    comments=None,
    views=None,
    viewers=None,
):
    if not ad_id:
        return

    rented_node = get_node(data["categories"], "rented")
    if not rented_node:
        return

    for r in rented_node.get("items", []):
        if r.get("ad_id") == ad_id:
            if text is not None:
                r["text"] = text
            if photos is not None:
                r["photos"] = photos
            if videos is not None:
                r["videos"] = videos
            if documents is not None:
                r["documents"] = documents
            if origin_path is not None:
                r["origin_path"] = origin_path
            if report_phone is not None:
                r["report_phone"] = report_phone
            if report_location is not None:
                r["report_location"] = report_location
            if comments_enabled is not None:
                r["comments_enabled"] = comments_enabled
            if comments is not None:
                r["comments"] = comments
            if views is not None:
                r["views"] = views
            if viewers is not None:
                r["viewers"] = viewers
            break


# =====================================================
# الكيبورد الإضافي تحت الإعلان
# =====================================================

def get_extra_keyboard(path, idx, admin, user_id=None):
    data = load_data()
    node = get_node(data["categories"], path)

    if not node:
        return None

    items = node.get("items", [])
    if idx >= len(items):
        return None

    item = items[idx]
    global_comments = comments_globally_enabled()
    item_comments_enabled = bool(item.get("comments_enabled", True))
    effective_comments_enabled = global_comments and item_comments_enabled
    comments_count = len(item.get("comments", []))

    write_label = "💬 كتابة تعليق" if effective_comments_enabled else "🔒 التعليقات مغلقة"
    view_label = f"📝 إظهار التعليقات ({comments_count})"

    # للضيف: فقط كتابة تعليق
    if not admin:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(write_label, callback_data=f"comment:add:{path}:{idx}")
            ]
        ])

    user_drawers = drawer_states.setdefault(user_id, {})
    opened = user_drawers.get((path, idx), False)

    # ===== drawer مغلق =====
    if not opened:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔻 إدارة", callback_data=f"drawer:open:{path}:{idx}")],
            [InlineKeyboardButton("────────────", callback_data="ignore")],
            [
                InlineKeyboardButton(write_label, callback_data=f"comment:add:{path}:{idx}"),
                InlineKeyboardButton(view_label, callback_data=f"comment:view:{path}:{idx}")
            ],
            [
                InlineKeyboardButton("✏️ تعديل إعلان", callback_data=f"edit:{path}:{idx}"),
                InlineKeyboardButton("🗑 حذف الإعلان", callback_data=f"quickdel:{path}:{idx}")
            ],
            [InlineKeyboardButton("🔁 نقل الإعلان", callback_data=f"move:start:{path}:{idx}")]
        ])

    # ===== drawer مفتوح =====
    status = item.get("status", "free")
    free_label = "☑ غير مؤجر" if status == "free" else "⬜ غير مؤجر"
    rented_label = "☑ مؤجر" if status == "rented" else "⬜ مؤجر"
    comments_toggle_label = "🔒 غلق التعليقات" if item_comments_enabled else "🔓 فتح التعليقات"

    global_label = "🌐 التعليقات العامة: مفتوحة" if global_comments else "🌐 التعليقات العامة: مغلقة"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔺 إدارة", callback_data=f"drawer:close:{path}:{idx}")],
        [
            InlineKeyboardButton(free_label, callback_data=f"status:free:{path}:{idx}"),
            InlineKeyboardButton(rented_label, callback_data=f"status:rented:{path}:{idx}")
        ],
        [
            InlineKeyboardButton(write_label, callback_data=f"comment:add:{path}:{idx}"),
            InlineKeyboardButton(view_label, callback_data=f"comment:view:{path}:{idx}")
        ],
        [InlineKeyboardButton(comments_toggle_label, callback_data=f"comment:toggle:{path}:{idx}")],
        [InlineKeyboardButton(global_label, callback_data="ignore")],
        [InlineKeyboardButton("────────────", callback_data="ignore")],
        [
            InlineKeyboardButton("✏️ تعديل إعلان", callback_data=f"edit:{path}:{idx}"),
            InlineKeyboardButton("🗑 حذف الإعلان", callback_data=f"quickdel:{path}:{idx}")
        ],
        [InlineKeyboardButton("🔁 نقل الإعلان", callback_data=f"move:start:{path}:{idx}")]
    ])


# =====================================================
# تحقق إداري
# =====================================================

def is_admin_user(user_id):
    config = load_config()

    admin_id = config.get("ADMIN_ID")
    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        admin_id = None

    admins = config.get("ADMINS", [])
    admins = [int(a) for a in admins if str(a).isdigit()]

    return user_id == admin_id or user_id in admins


# =====================================================
# تحديث مباشر عند جميع المستخدمين (للمسار الأصلي)
# =====================================================

async def refresh_everywhere(context, path, idx):
    data = load_data()
    node = get_node(data["categories"], path)

    if not node:
        return

    items = node.get("items", [])
    if idx >= len(items):
        return

    views_count = int(items[idx].get("views", 0) or 0)
    comments_count = len(items[idx].get("comments", []))
    text = (
        f"#{idx + 1}\n"
        f"👁️ المشاهدات: {views_count}\n"
        f"💬 التعليقات: {comments_count}\n"
        f"{items[idx].get('text', '')}"
    )
    targets = ad_message_map.get(path, {}).get(idx, [])

    config = load_config()
    admin_id = config.get("ADMIN_ID")
    admins = config.get("ADMINS", [])

    for chat_id, message_id, owner_id in targets:
        try:
            is_admin = (owner_id == admin_id or owner_id in admins)

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=get_extra_keyboard(
                    path,
                    idx,
                    is_admin,
                    owner_id
                )
            )
        except Exception:
            pass


# =====================================================
# بناء كيبورد النقل (Navigation-based)
# =====================================================

def build_move_keyboard(categories, current_path):
    node = get_node(categories, current_path) if current_path else {"sub": categories}

    if not node:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="move:cancel")]
        ])

    keyboard = []

    if current_path:
        parent = "/".join(current_path.split("/")[:-1])
        nav_id = register_path(parent)
        keyboard.append([InlineKeyboardButton("⬅ رجوع", callback_data=f"move:nav:{nav_id}")])
    else:
        keyboard.append([InlineKeyboardButton("⬅ رجوع", callback_data="move:cancel")])

    subs = node.get("sub", {})
    for key, child in subs.items():
        next_path = f"{current_path}/{key}" if current_path else key
        nav_id = register_path(next_path)
        keyboard.append([
            InlineKeyboardButton(child.get("title", key), callback_data=f"move:nav:{nav_id}")
        ])

    if current_path and not subs:
        nav_id = register_path(current_path)
        keyboard.append([InlineKeyboardButton("✅ نقل هنا", callback_data=f"move:confirm:{nav_id}")])

    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="move:cancel")])

    return InlineKeyboardMarkup(keyboard)


# =====================================================
# تحديث مباشر لرسائل المؤجر (حسب ad_id)
# =====================================================

def find_rented_index(data, ad_id):
    rented_node = get_node(data["categories"], "rented")
    if not rented_node:
        return None

    items = rented_node.get("items", [])
    for i, r in enumerate(items):
        if r.get("ad_id") == ad_id:
            return i

    return None


async def refresh_rented_everywhere(context, ad_id):
    if not ad_id:
        return

    data = load_data()
    ridx = find_rented_index(data, ad_id)
    if ridx is None:
        return

    rented_node = get_node(data["categories"], "rented")
    if not rented_node:
        return

    items = rented_node.get("items", [])
    if ridx >= len(items):
        return

    views_count = int(items[ridx].get("views", 0) or 0)
    comments_count = len(items[ridx].get("comments", []))
    text = (
        f"#{ridx + 1}\n"
        f"👁️ المشاهدات: {views_count}\n"
        f"💬 التعليقات: {comments_count}\n"
        f"{items[ridx].get('text', '')}"
    )
    targets = ad_message_map.get("rented", {}).get(ridx, [])

    config = load_config()
    admin_id = config.get("ADMIN_ID")
    admins = config.get("ADMINS", [])

    for chat_id, message_id, owner_id in targets:
        try:
            is_admin = (owner_id == admin_id or owner_id in admins)

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=get_extra_keyboard(
                    "rented",
                    ridx,
                    is_admin,
                    owner_id
                )
            )
        except Exception:
            pass


# =====================================================
# تنسيق التعليقات
# =====================================================

def _format_comments_block(comments):
    if not comments:
        return "لا توجد تعليقات بعد."

    lines = []
    for i, c in enumerate(comments[-10:], start=1):
        name = c.get("name") or "مستخدم"
        text = c.get("text") or ""
        created_at = c.get("created_at") or ""
        lines.append(f"{i}) {name}\n{text}\n🕒 {created_at}")
    return "\n\n".join(lines)


async def _delete_comment_prompt(context, user_id):
    info = comment_prompt_messages.pop(user_id, None)
    if not info:
        return

    try:
        await context.bot.delete_message(
            chat_id=info["chat_id"],
            message_id=info["message_id"]
        )
    except Exception:
        pass


async def _delete_comment_view(context, user_id, path, idx):
    key = (user_id, path, idx)
    info = open_comment_views.pop(key, None)
    if not info:
        return

    try:
        await context.bot.delete_message(
            chat_id=info["chat_id"],
            message_id=info["message_id"]
        )
    except Exception:
        pass


# =====================================================
# الهاندلر الرئيسي
# =====================================================

async def handle_extra(update, context):
    if not update.callback_query or not update.callback_query.data:
        return

    query = update.callback_query
    data_cb = query.data
    user_id = query.from_user.id

    if data_cb == "ignore":
        try:
            await query.answer()
        except Exception:
            pass
        return

    # =========================
    # التعليقات (للجميع)
    # =========================
    if data_cb.startswith("comment:add:"):
        try:
            await query.answer()
        except Exception:
            pass

        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        data = load_data()
        node = get_node(data["categories"], path)
        if not node:
            return

        items = node.get("items", [])
        if idx >= len(items):
            return

        item = items[idx]

        if not comments_globally_enabled():
            await query.message.reply_text("🔒 التعليقات مغلقة حاليًا على كل الإعلانات.")
            return

        if not item.get("comments_enabled", True):
            await query.message.reply_text("🔒 التعليقات مغلقة لهذا الإعلان.")
            return

        await _delete_comment_prompt(context, user_id)

        comment_sessions[user_id] = {"path": path, "idx": idx}

        sent = await query.message.reply_text(
            "✍️ اكتب تعليقك الآن على هذا الإعلان:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء التعليق", callback_data=f"comment:cancel:{path}:{idx}")]
            ])
        )

        comment_prompt_messages[user_id] = {
            "chat_id": sent.chat_id,
            "message_id": sent.message_id,
            "path": path,
            "idx": idx,
        }
        return

    if data_cb.startswith("comment:cancel:"):
        try:
            await query.answer()
        except Exception:
            pass

        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        sess = comment_sessions.get(user_id)
        if sess and sess.get("path") == path and sess.get("idx") == idx:
            comment_sessions.pop(user_id, None)

        await _delete_comment_prompt(context, user_id)
        return

    if data_cb.startswith("comment:view:"):
        try:
            await query.answer()
        except Exception:
            pass

        # إظهار التعليقات للأدمن فقط
        if not is_admin_user(user_id):
            return

        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        data = load_data()
        node = get_node(data["categories"], path)
        if not node:
            return

        items = node.get("items", [])
        if idx >= len(items):
            return

        await _delete_comment_view(context, user_id, path, idx)

        comments = items[idx].get("comments", [])
        title = _short_title_from_text(items[idx].get("text", ""))
        text = f"📝 تعليقات الإعلان\n{title}\n\n{_format_comments_block(comments)}"

        sent = await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إخفاء التعليقات", callback_data=f"comment:hide:{path}:{idx}")]
            ])
        )

        open_comment_views[(user_id, path, idx)] = {
            "chat_id": sent.chat_id,
            "message_id": sent.message_id,
        }
        return

    if data_cb.startswith("comment:hide:"):
        try:
            await query.answer()
        except Exception:
            pass

        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        await _delete_comment_view(context, user_id, path, idx)
        return

    if data_cb.startswith("comment:toggle:"):
        try:
            await query.answer()
        except Exception:
            pass

        if not is_admin_user(user_id):
            return

        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        data = load_data()
        node = get_node(data["categories"], path)
        if not node:
            return

        items = node.get("items", [])
        if idx >= len(items):
            return

        current = bool(items[idx].get("comments_enabled", True))
        items[idx]["comments_enabled"] = not current

        ad_id = items[idx].get("ad_id")
        if ad_id:
            sync_rented_item(
                data,
                ad_id,
                comments_enabled=items[idx].get("comments_enabled", True),
                comments=items[idx].get("comments", []),
                views=int(items[idx].get("views", 0) or 0),
                viewers=items[idx].get("viewers", []),
                report_phone=items[idx].get("report_phone", ""),
                report_location=items[idx].get("report_location", ""),
            )

        save_data(data)
        await refresh_everywhere(context, path, idx)
        await refresh_rented_everywhere(context, ad_id)

        msg = "✅ تم فتح التعليقات" if items[idx]["comments_enabled"] else "✅ تم غلق التعليقات"
        await query.message.reply_text(msg)
        return

    # من هنا وما بعده أوامر الإدارة فقط
    if not is_admin_user(user_id):
        try:
            await query.answer()
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass

    # ===== Drawer Open =====
    if data_cb.startswith("drawer:open:"):
        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        drawer_states.setdefault(user_id, {})[(path, idx)] = True
        await query.message.edit_reply_markup(
            reply_markup=get_extra_keyboard(path, idx, True, user_id)
        )
        return

    # ===== Drawer Close =====
    if data_cb.startswith("drawer:close:"):
        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, path, idx = parts
        idx = int(idx)

        drawer_states.setdefault(user_id, {})[(path, idx)] = False
        await query.message.edit_reply_markup(
            reply_markup=get_extra_keyboard(path, idx, True, user_id)
        )
        return

    # =========================
    # نقل إعلان بين اللستات
    # =========================
    if data_cb.startswith("move:start:"):
        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, _, from_path, idx = parts
        idx = int(idx)

        move_sessions[user_id] = {
            "from_path": from_path,
            "idx": idx,
            "current_path": ""
        }

        data = load_data()
        kb = build_move_keyboard(data["categories"], "")

        await query.message.reply_text(
            "🔁 اختر اللستة المراد نقل الإعلان إليها:",
            reply_markup=kb
        )
        return

    if data_cb.startswith("move:nav:"):
        parts = data_cb.split(":", 2)
        if len(parts) != 3:
            return

        _, _, nav_id = parts
        current_path = get_path(nav_id)

        if user_id not in move_sessions:
            return

        move_sessions[user_id]["current_path"] = current_path or ""

        data = load_data()
        kb = build_move_keyboard(data["categories"], move_sessions[user_id]["current_path"])
        await query.message.edit_reply_markup(reply_markup=kb)
        return

    if data_cb.startswith("move:confirm:"):
        if user_id not in move_sessions:
            return

        parts = data_cb.split(":", 2)
        if len(parts) != 3:
            return

        _, _, nav_id = parts
        to_path = get_path(nav_id)

        from_path = move_sessions[user_id]["from_path"]
        idx = move_sessions[user_id]["idx"]

        if not to_path:
            return

        data = load_data()
        from_node = get_node(data["categories"], from_path)
        to_node = get_node(data["categories"], to_path)

        if not from_node or not to_node:
            move_sessions.pop(user_id, None)
            await query.message.reply_text("❌ خطأ بالمسار")
            return

        from_items = from_node.get("items", [])
        to_node.setdefault("items", [])

        if idx >= len(from_items):
            move_sessions.pop(user_id, None)
            await query.message.reply_text("❌ الإعلان غير موجود")
            return

        if from_path == to_path:
            move_sessions.pop(user_id, None)
            await query.message.reply_text("ℹ️ نفس اللستة، ماكو نقل")
            return

        item = from_items.pop(idx)
        to_node["items"].append(item)

        if item.get("status") == "rented" and item.get("ad_id"):
            sync_rented_item(
                data,
                item.get("ad_id"),
                origin_path=to_path,
                report_phone=item.get("report_phone", ""),
                report_location=item.get("report_location", ""),
                comments_enabled=item.get("comments_enabled", True),
                comments=item.get("comments", []),
                views=int(item.get("views", 0) or 0),
                viewers=item.get("viewers", []),
            )

        save_data(data)

        try:
            await update_listing_in_channel(context, item, notify_guests=False)
        except Exception:
            pass

        try:
            title = _short_title_from_text(item.get("text", ""))
            await notify_subscribers(
                context,
                f"🔁 تم نقل إعلان: {title}",
                ad_link=_tg_ad_link(item.get("ad_id"))
            )
        except Exception:
            pass

        move_sessions.pop(user_id, None)

        await query.message.reply_text("✅ تم نقل الإعلان بنجاح")

        from commands.menu import render_ads
        await render_ads(context, update.callback_query, from_path, True)
        return

    if data_cb == "move:cancel":
        move_sessions.pop(user_id, None)
        await query.message.reply_text("❌ تم إلغاء النقل")
        return

    # =========================
    # تغيير الحالة
    # =========================
    if data_cb.startswith("status:"):
        parts = data_cb.split(":", 3)
        if len(parts) != 4:
            return

        _, status, path, idx = parts
        idx = int(idx)

        data = load_data()
        node = get_node(data["categories"], path)
        if not node:
            return

        items = node.get("items", [])
        if idx >= len(items):
            return

        if path == "rented":
            rented_item = items[idx]
            ad_id = rented_item.get("ad_id")
            origin_path = rented_item.get("origin_path")

            if not ad_id or not origin_path:
                return

            origin_node = get_node(data["categories"], origin_path)
            if not origin_node:
                return

            origin_items = origin_node.get("items", [])
            origin_idx = None
            for i, it in enumerate(origin_items):
                if it.get("ad_id") == ad_id:
                    origin_idx = i
                    break

            if origin_idx is None:
                return

            origin_items[origin_idx]["status"] = status

            rented_node = get_node(data["categories"], "rented")
            if rented_node:
                rented_node.setdefault("items", [])

                if status == "free":
                    rented_node["items"] = [
                        x for x in rented_node.get("items", [])
                        if x.get("ad_id") != ad_id
                    ]
                else:
                    sync_rented_item(
                        data,
                        ad_id,
                        text=origin_items[origin_idx].get("text", ""),
                        photos=origin_items[origin_idx].get("photos", []),
                        videos=origin_items[origin_idx].get("videos", []),
                        documents=origin_items[origin_idx].get("documents", []),
                        origin_path=origin_path,
                        report_phone=origin_items[origin_idx].get("report_phone", ""),
                        report_location=origin_items[origin_idx].get("report_location", ""),
                        comments_enabled=origin_items[origin_idx].get("comments_enabled", True),
                        comments=origin_items[origin_idx].get("comments", []),
                        views=int(origin_items[origin_idx].get("views", 0) or 0),
                        viewers=origin_items[origin_idx].get("viewers", []),
                    )

            save_data(data)

            try:
                if status == "free":
                    await delete_listing_from_channel(context, ad_id)
                    await publish_listing_to_channel(context, origin_items[origin_idx], notify_guests=False)
                else:
                    await publish_listing_to_channel(context, origin_items[origin_idx], notify_guests=False)
            except Exception:
                pass

            from commands.menu import render_ads
            await render_ads(context, update.callback_query, "rented", True)
            return

        if "ad_id" not in items[idx] or not items[idx].get("ad_id"):
            import uuid
            items[idx]["ad_id"] = uuid.uuid4().hex

        ad_id = items[idx]["ad_id"]
        items[idx]["status"] = status

        rented_node = get_node(data["categories"], "rented")
        if rented_node:
            rented_node.setdefault("items", [])

            if status == "rented":
                src = items[idx]
                exists = any(x.get("ad_id") == ad_id for x in rented_node["items"])

                if not exists:
                    rented_node["items"].append({
                        "ad_id": ad_id,
                        "origin_path": path,
                        "text": src.get("text", ""),
                        "photos": src.get("photos", []),
                        "videos": src.get("videos", []),
                        "documents": src.get("documents", []),
                        "status": "rented",
                        "report_phone": src.get("report_phone", ""),
                        "report_location": src.get("report_location", ""),
                        "comments_enabled": src.get("comments_enabled", True),
                        "comments": src.get("comments", []),
                        "views": int(src.get("views", 0) or 0),
                        "viewers": src.get("viewers", []),
                    })
                else:
                    sync_rented_item(
                        data,
                        ad_id,
                        text=src.get("text", ""),
                        photos=src.get("photos", []),
                        videos=src.get("videos", []),
                        documents=src.get("documents", []),
                        origin_path=path,
                        report_phone=src.get("report_phone", ""),
                        report_location=src.get("report_location", ""),
                        comments_enabled=src.get("comments_enabled", True),
                        comments=src.get("comments", []),
                        views=int(src.get("views", 0) or 0),
                        viewers=src.get("viewers", []),
                    )

            elif status == "free":
                rented_node["items"] = [
                    x for x in rented_node.get("items", [])
                    if x.get("ad_id") != ad_id
                ]

        save_data(data)

        try:
            if status == "rented":
                await delete_listing_from_channel(context, ad_id)
            elif status == "free":
                await publish_listing_to_channel(context, items[idx], notify_guests=False)
        except Exception:
            pass

        from commands.menu import render_ads
        await render_ads(context, update.callback_query, path, True)
        return

    # =========================
    # حذف سريع للإعلان
    # =========================
    if data_cb.startswith("quickdel:"):
        parts = data_cb.split(":", 2)
        if len(parts) != 3:
            return

        _, path, idx = parts
        idx = int(idx)

        data = load_data()
        node = get_node(data["categories"], path)
        if not node:
            return

        items = node.get("items", [])
        if idx >= len(items):
            return

        removed = items.pop(idx)
        ad_id = removed.get("ad_id")

        if ad_id:
            rented_node = get_node(data["categories"], "rented")
            if rented_node:
                rented_node["items"] = [
                    x for x in rented_node.get("items", [])
                    if x.get("ad_id") != ad_id
                ]

        save_data(data)

        try:
            await delete_listing_from_channel(context, ad_id)
        except Exception:
            pass

#        try:
#            title = _short_title_from_text(removed.get("text", ""))
#            await notify_subscribers(
#                context,
#                f"🗑 تم حذف إعلان: {title}",
#                ad_link=None
#            )
#        except Exception:
#            pass

        await query.message.reply_text("✅ تم حذف الإعلان بالكامل")

        from commands.menu import render_ads
        await render_ads(context, update.callback_query, path, True)
        return

    # =========================
    # بدء تعديل إعلان
    # =========================
    if data_cb.startswith("edit:"):
        parts = data_cb.split(":", 2)
        if len(parts) != 3:
            return

        _, path, idx = parts
        idx = int(idx)

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

    if data_cb == "editcancel":
        edit_sessions.pop(user_id, None)
        await query.message.reply_text("❌ تم إلغاء العملية")
        return


# =====================================================
# استقبال تعليق جديد
# =====================================================

async def handle_comment_text(update, context):
    user_id = update.effective_user.id

    if user_id not in comment_sessions:
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    session = comment_sessions.get(user_id)
    path = session["path"]
    idx = session["idx"]

    data = load_data()
    node = get_node(data["categories"], path)
    if not node:
        comment_sessions.pop(user_id, None)
        await _delete_comment_prompt(context, user_id)
        return

    items = node.get("items", [])
    if idx >= len(items):
        comment_sessions.pop(user_id, None)
        await _delete_comment_prompt(context, user_id)
        return

    if not comments_globally_enabled():
        comment_sessions.pop(user_id, None)
        await _delete_comment_prompt(context, user_id)
        await update.message.reply_text("🔒 التعليقات مغلقة حاليًا على كل الإعلانات.")
        return

    if not items[idx].get("comments_enabled", True):
        comment_sessions.pop(user_id, None)
        await _delete_comment_prompt(context, user_id)
        await update.message.reply_text("🔒 التعليقات مغلقة لهذا الإعلان.")
        return

    items[idx].setdefault("comments", [])
    items[idx]["comments"].append({
        "user_id": user_id,
        "name": update.effective_user.first_name or "مستخدم",
        "text": text,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    ad_id = items[idx].get("ad_id")
    if ad_id:
        sync_rented_item(
            data,
            ad_id,
            comments=items[idx].get("comments", []),
            comments_enabled=items[idx].get("comments_enabled", True),
            views=int(items[idx].get("views", 0) or 0),
            viewers=items[idx].get("viewers", []),
            report_phone=items[idx].get("report_phone", ""),
            report_location=items[idx].get("report_location", ""),
        )

    save_data(data)
    comment_sessions.pop(user_id, None)
    await _delete_comment_prompt(context, user_id)

    await update.message.reply_text("✅ تم حفظ تعليقك")


# =====================================================
# استقبال النص الجديد (التعديل)
# =====================================================

async def handle_edit_text(update, context):
    user_id = update.effective_user.id

    if not is_admin_user(user_id):
        return

    if user_id not in edit_sessions:
        return

    session = edit_sessions[user_id]
    if session["step"] != "text":
        return

    new_text = update.message.text.strip()
    if not new_text:
        return

    data = load_data()
    node = get_node(data["categories"], session["path"])
    if not node:
        return

    items = node.get("items", [])
    if session["idx"] >= len(items):
        edit_sessions.pop(user_id, None)
        return

    items[session["idx"]]["text"] = new_text

    ad_id = items[session["idx"]].get("ad_id")
    if ad_id:
        sync_rented_item(
            data,
            ad_id,
            text=new_text,
            report_phone=items[session["idx"]].get("report_phone", ""),
            report_location=items[session["idx"]].get("report_location", ""),
            comments_enabled=items[session["idx"]].get("comments_enabled", True),
            comments=items[session["idx"]].get("comments", []),
            views=int(items[session["idx"]].get("views", 0) or 0),
            viewers=items[session["idx"]].get("viewers", []),
        )

    save_data(data)

    try:
        await update_listing_in_channel(context, items[session["idx"]], notify_guests=False)
    except Exception:
        pass

    try:
        title = _short_title_from_text(new_text)
        await notify_subscribers(
            context,
            f"✏️ تم تعديل إعلان: {title}",
            ad_link=_tg_ad_link(ad_id)
        )
    except Exception:
        pass

    await refresh_everywhere(context, session["path"], session["idx"])
    await refresh_rented_everywhere(context, ad_id)

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
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id

    if not is_admin_user(user_id):
        return

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
            "📸 أرسل الصور الجديدة ثم اضغط (✅ تم)",
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

        items = node.get("items", [])
        if session["idx"] >= len(items):
            edit_sessions.pop(user_id, None)
            return

        new_photos = session.get("photos", [])
        items[session["idx"]]["photos"] = new_photos

        ad_id = items[session["idx"]].get("ad_id")
        if ad_id:
            sync_rented_item(
                data,
                ad_id,
                photos=new_photos,
                report_phone=items[session["idx"]].get("report_phone", ""),
                report_location=items[session["idx"]].get("report_location", ""),
                comments_enabled=items[session["idx"]].get("comments_enabled", True),
                comments=items[session["idx"]].get("comments", []),
                views=int(items[session["idx"]].get("views", 0) or 0),
                viewers=items[session["idx"]].get("viewers", []),
            )

        save_data(data)

        try:
            await update_listing_in_channel(context, items[session["idx"]], notify_guests=False)
        except Exception:
            pass

        try:
            title = _short_title_from_text(items[session["idx"]].get("text", ""))
            await notify_subscribers(
                context,
                f"🖼 تم تحديث صور إعلان: {title}",
                ad_link=_tg_ad_link(ad_id)
            )
        except Exception:
            pass

        await refresh_everywhere(context, session["path"], session["idx"])
        await refresh_rented_everywhere(context, ad_id)

        edit_sessions.pop(user_id, None)
        await query.message.reply_text("✅ تم تحديث الصور")
        return


# =====================================================
# استقبال الصور الجديدة
# =====================================================

async def handle_new_photos(update, context):
    user_id = update.effective_user.id

    if not is_admin_user(user_id):
        return

    if user_id not in edit_sessions:
        return

    session = edit_sessions[user_id]
    if session["step"] != "new_photos":
        return

    if not update.message.photo:
        return

    photo = update.message.photo[-1]
    session.setdefault("photos", []).append(photo.file_id)

    await update.message.reply_text("📷 تم حفظ الصورة")


# =====================================================
# تسجيل الهاندلرات
# =====================================================

def register(app):
    app.add_handler(
        CallbackQueryHandler(
            handle_extra,
            pattern="^(status:|edit:|editcancel|ignore|quickdel:|drawer:|move:|comment:)"
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
            handle_comment_text
        ),
        group=8
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_edit_text
        ),
        group=9
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_new_photos
        )
    )

    app.add_handler(CommandHandler("open_comments_all", open_comments_all_cmd))
    app.add_handler(CommandHandler("close_comments_all", close_comments_all_cmd))
