from telegram.ext import CommandHandler
from settings import load_config


def is_admin(update):
    config = load_config()
    return update.effective_user.id == config.get("ADMIN_ID")


async def help_cmd(update, context):
    user = update.effective_user

    public_text = (
        "🤖 مرحبًا بك في بوت عقارات أبو الحسن\n\n"
        "الأوامر المتاحة لك:\n"
        "/start - تشغيل البوت وعرض الأقسام\n"
        "/help - عرض هذه المساعدة\n\n"
        "كيف تستخدم البوت:\n"
        "1) اختر القسم (إيجارات / بيع / خدمات)\n"
        "2) اختر اللستة المناسبة\n"
        "3) تصفّح الإعلانات والصور\n\n"
        "💬 للتواصل اختر زر واتساب من القائمة الرئيسية"
    )

    admin_text = (
        "🛠 لوحة إدارة البوت\n\n"
        "أوامر الإدارة:\n"
        "/add - إضافة إعلان جديد\n"
        "/add_list - إضافة لستة داخل قسم\n"
        "/delete_list - حذف لستة\n\n"
        "تلميحات سريعة:\n"
        "• استخدم 🗑 إدارة الحذف داخل أي لستة لحذف عدة إعلانات مرة واحدة\n"
        "• زر ⬅ رجوع يعيدك دائمًا للقائمة السابقة\n"
        "• أي تعديل يُحفظ تلقائيًا في ملف البيانات\n"
    )

    if is_admin(update):
        await update.message.reply_text(admin_text)
    else:
        await update.message.reply_text(public_text)


def register(app):
    app.add_handler(CommandHandler("help", help_cmd))