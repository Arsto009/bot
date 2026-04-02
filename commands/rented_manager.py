import uuid

from telegram.ext import CallbackQueryHandler, CommandHandler

from services.storage import load_data, save_data
from settings import load_config
from commands.shared_ads import get_node


def is_admin(user_id):
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
# أدوات مساعدة
# =====================================================

def ensure_ad_id(item):
    if "ad_id" not in item or not item.get("ad_id"):
        item["ad_id"] = uuid.uuid4().hex
    return item["ad_id"]


def rebuild_rented_list(data):
    categories = data.get("categories", {})
    rented_node = get_node(categories, "rented")
    if not rented_node:
        return False, "⚠️ لستة المؤجر غير موجودة."

    rented_node["items"] = []

    def walk(node, path):
        items = node.get("items")
        subs = node.get("sub", {})

        # leaf حقيقي: عنده items وما عنده sub
        if isinstance(items, list) and not subs:
            for item in items:
                if item.get("status", "free") == "rented":
                    ad_id = ensure_ad_id(item)
                    rented_node["items"].append({
                        "ad_id": ad_id,
                        "origin_path": path,
                        "text": item.get("text", ""),
                        "photos": item.get("photos", []),
                        "videos": item.get("videos", []),
                        "documents": item.get("documents", []),
                        "status": "rented"
                    })

        for k, child in subs.items():
            next_path = f"{path}/{k}" if path else k
            walk(child, next_path)

    for k, cat in categories.items():
        if k == "rented":
            continue
        walk(cat, k)

    return True, f"✅ تم إعادة بناء المؤجر. عدد المؤجر: {len(rented_node['items'])}"


# =====================================================
# حذف المؤجر + حذف من الأصل
# =====================================================

async def rented_clear_yes(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    data = load_data()

    rented_node = get_node(data["categories"], "rented")
    if not rented_node:
        await query.message.reply_text("⚠️ لستة المؤجر غير موجودة.")
        return

    rented_items = rented_node.get("items", [])

    for r in rented_items:
        ad_id = r.get("ad_id")
        origin_path = r.get("origin_path")

        if not ad_id or not origin_path:
            continue

        origin_node = get_node(data["categories"], origin_path)
        if not origin_node:
            continue

        if isinstance(origin_node.get("items"), list):
            origin_node["items"] = [
                x for x in origin_node["items"]
                if x.get("ad_id") != ad_id
            ]

    rented_node["items"] = []
    save_data(data)

    await query.message.reply_text("✅ تم حذف الكلايش من المؤجر ومن اللستات الأصلية.")

    from commands.menu import render_ads
    await render_ads(context, query, "rented", True)


async def rented_clear_no(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    await query.message.reply_text("❌ تم إلغاء العملية.")


# =====================================================
# /rented_rebuild
# =====================================================

async def rented_rebuild_cmd(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر للإدارة فقط.")
        return

    data = load_data()
    ok, msg = rebuild_rented_list(data)
    if not ok:
        await update.message.reply_text(msg)
        return

    save_data(data)
    await update.message.reply_text(msg)


# =====================================================
# Register
# =====================================================

def register(app):
    app.add_handler(CallbackQueryHandler(rented_clear_yes, pattern="^rented_clear:yes$"))
    app.add_handler(CallbackQueryHandler(rented_clear_no, pattern="^rented_clear:no$"))
    app.add_handler(CommandHandler("rented_rebuild", rented_rebuild_cmd))