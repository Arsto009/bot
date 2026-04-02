from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from services.storage import load_data, save_data
from commands.shared_ads import get_node
from settings import load_config


# =========================
# تحقق أدمن
# =========================
def is_admin(user_id):
    config = load_config()
    return (
        user_id == config.get("ADMIN_ID")
        or user_id in config.get("ADMINS", [])
    )


# =========================
# نسخ إعلان إلى المؤجر
# =========================
async def add_to_rented(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    # rentedadd:{path}:{idx}
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        return

    _, path, idx = parts
    idx = int(idx)

    data = load_data()

    source_node = get_node(data["categories"], path)
    rented_node = get_node(data["categories"], "rented")

    if not source_node or not rented_node:
        return

    items = source_node.get("items", [])
    if idx >= len(items):
        return

    item = items[idx].copy()

    # حفظ المصدر حتى نحذف منه لاحقاً
    item["_origin_path"] = path
    item["_origin_idx"] = idx

    rented_node.setdefault("items", []).append(item)
    save_data(data)

    await query.message.reply_text("✅ تم إضافة الإعلان إلى المؤجر")


# =========================
# سؤال الحذف (داخل المؤجر)
# =========================
async def rented_delete_prompt(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    # rentedask:{idx}
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return

    _, idx = parts
    idx = int(idx)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("نعم", callback_data=f"rented_yes:{idx}"),
            InlineKeyboardButton("لا", callback_data="rented_no")
        ]
    ])

    await query.message.reply_text(
        "هل تريد حذف الكلايش المؤجرة؟",
        reply_markup=kb
    )


# =========================
# نعم (حذف من المؤجر + المصدر)
# =========================
async def rented_yes(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    # rented_yes:{idx}
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return

    _, idx = parts
    idx = int(idx)

    data = load_data()
    rented_node = get_node(data["categories"], "rented")

    if not rented_node:
        return

    items = rented_node.get("items", [])
    if idx >= len(items):
        return

    item = items.pop(idx)

    origin_path = item.get("_origin_path")
    origin_idx = item.get("_origin_idx")

    # حذف من المصدر (إذا موجود)
    if origin_path is not None and origin_idx is not None:
        origin_node = get_node(data["categories"], origin_path)
        if origin_node:
            origin_items = origin_node.get("items", [])
            if isinstance(origin_idx, int) and origin_idx < len(origin_items):
                origin_items.pop(origin_idx)

    save_data(data)

    await query.message.reply_text("✅ تم حذف الإعلان من المؤجر والمصدر")


# =========================
# لا (إلغاء + رجوع للرئيسية)
# =========================
async def rented_no(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    await query.message.reply_text("❌ تم إلغاء العملية. رجوع للرئيسية.")


# =========================
# Register
# =========================
def register(app):
    app.add_handler(CallbackQueryHandler(add_to_rented, pattern="^rentedadd:"))
    app.add_handler(CallbackQueryHandler(rented_delete_prompt, pattern="^rentedask:"))
    app.add_handler(CallbackQueryHandler(rented_yes, pattern="^rented_yes:"))
    app.add_handler(CallbackQueryHandler(rented_no, pattern="^rented_no$"))
