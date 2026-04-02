from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from settings import load_config
from services.storage import load_data


def is_admin_user(user_id: int) -> bool:
    cfg = load_config()
    admin_id = cfg.get("ADMIN_ID")
    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        admin_id = None

    admins = cfg.get("ADMINS", [])
    admins = [int(a) for a in admins if str(a).isdigit()]
    return user_id == admin_id or user_id in admins


def _short_title_from_text(text: str) -> str:
    if not text:
        return "إعلان"

    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "إعلان"

    first = lines[0]
    if len(first) > 55:
        first = first[:55] + "..."
    return first


def _collect_ads(data: dict):
    categories = data.get("categories", {}) or {}
    all_ads = []

    def walk(node, root_name=""):
        subs = node.get("sub", {}) or {}
        items = node.get("items", None)

        if isinstance(items, list):
            for it in items:
                item = dict(it)
                item["_root"] = root_name
                all_ads.append(item)

        for key, child in subs.items():
            walk(child, root_name)

    rent_root = categories.get("rent", {})
    sale_root = categories.get("sale", {})

    walk(rent_root, "rent")
    walk(sale_root, "sale")

    return all_ads


def _top_viewed(ad_list):
    if not ad_list:
        return None, 0

    top_ad = None
    max_views = -1

    for ad in ad_list:
        views = int(ad.get("views", 0) or 0)
        if views > max_views:
            max_views = views
            top_ad = ad

    return top_ad, max_views


async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin_user(uid):
        await update.message.reply_text("❌ هذا الأمر للإدارة فقط.")
        return

    data = load_data()
    info = data.get("info", {}) or {}
    business_name = info.get("business_name", "عقارات")

    ads = _collect_ads(data)

    rent_ads = [a for a in ads if a.get("_root") == "rent"]
    sale_ads = [a for a in ads if a.get("_root") == "sale"]

    total_ads = len(ads)
    rent_total = len(rent_ads)
    sale_total = len(sale_ads)

    top_rent, top_rent_views = _top_viewed(rent_ads)
    top_sale, top_sale_views = _top_viewed(sale_ads)

    if top_rent:
        rent_top_text = (
            f"👁️ أكثر إعلان إيجار مشاهدة: {top_rent_views}\n"
            f"📝 {_short_title_from_text(top_rent.get('text', ''))}"
        )
    else:
        rent_top_text = "👁️ أكثر إعلان إيجار مشاهدة: لا يوجد بعد"

    if top_sale:
        sale_top_text = (
            f"👁️ أكثر إعلان بيع مشاهدة: {top_sale_views}\n"
            f"📝 {_short_title_from_text(top_sale.get('text', ''))}"
        )
    else:
        sale_top_text = "👁️ أكثر إعلان بيع مشاهدة: لا يوجد بعد"

    msg = (
        f"📊 لوحة متابعة العقارات\n"
        f"🏢 {business_name}\n\n"
        f"🏠 إجمالي إعلانات الإيجار: {rent_total}\n"
        f"🏷️ إجمالي إعلانات البيع: {sale_total}\n"
        f"📦 إجمالي جميع الإعلانات: {total_ads}\n\n"
        f"{rent_top_text}\n\n"
        f"{sale_top_text}"
    )

    await update.message.reply_text(msg)


def register(app):
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))