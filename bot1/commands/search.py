from telegram.ext import MessageHandler, filters
from services.storage import load_data
from commands.menu_extra import edit_sessions  # ✅ الاستيراد الصحيح
from commands.devpanel import sessions as dev_sessions


async def search(update, context):

    user_id = update.effective_user.id

    # لا تبحث أثناء تعديل إعلان
    if user_id in edit_sessions:
        return

    # لا تبحث أثناء جلسة لوحة المطور (إدخال كلمة السر)
    if user_id in dev_sessions:
        return


    if (
        not update.message
        or not update.message.text
        or update.message.reply_to_message
    ):
        return


    query = update.message.text.strip()

    # لا تبحث إذا النص أقل من 3 حروف
    if len(query) < 3:
        return

    query = query.lower()
    data = load_data()
    results = []    def scan_node(node):        # فحص الإعلانات داخل العقدة        for item in node.get("items", []):            if query in item.get("text", "").lower():                results.append(item)        # النزول لكل sub مهما كان العمق        for child in node.get("sub", {}).values():            scan_node(child)    # بدء الفحص من الجذر    for cat in data["categories"].values():        scan_node(cat)

    if not results:
        return

    for r in results[:5]:
        await update.message.reply_text(
            f"🏠 نتيجة:\n{r.get('text','')}"
        )


def register(app):
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search),
        group=5
    )