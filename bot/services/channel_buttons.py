from telegram import InlineKeyboardButton


def build_channel_notification_buttons(post_link=None):
    row = []

    if post_link:
        row.append(InlineKeyboardButton("إظهار", url=post_link))

    row.append(InlineKeyboardButton("تجاهل", callback_data="ignore_notification"))

    return [row]


async def handle_notification_action(update, context):
    query = getattr(update, "callback_query", None)
    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "ignore_notification":
        try:
            await query.message.delete()
        except Exception:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass