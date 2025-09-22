import os
from aiogram import Dispatcher
from aiogram.types import CallbackQuery

from bot.database.methods import (
    check_role,
    get_all_category_names,
    get_all_subcategories,
    get_all_item_names,
    get_category_parent,
    get_item_values,
    get_item_value_by_id,
    buy_item,
    select_item_values_amount,
    get_item_info,
)
from bot.database.models import Permission
from bot.handlers.other import get_bot_user_ids
from bot.keyboards import (
    stock_categories_list,
    stock_goods_list,
    stock_values_list,
    stock_value_actions,
)
from bot.misc import TgConfig
from bot.utils import display_name


async def view_stock_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = None
    role = check_role(user_id)
    if role & Permission.OWN:
        categories = get_all_category_names()
        lines = ['📋 Stock list']
        for category in categories:
            lines.append(f"\n<b>{category}</b>")
            for sub in get_all_subcategories(category):
                lines.append(f"  {sub}")
                for item in get_all_item_names(sub):
                    info = get_item_info(item)
                    count = select_item_values_amount(item)
                    lines.append(f"    • {display_name(item)} ({info['price']:.2f}€, {count})")
            for item in get_all_item_names(category):
                info = get_item_info(item)
                count = select_item_values_amount(item)
                lines.append(f"  • {display_name(item)} ({info['price']:.2f}€, {count})")
        text = '\n'.join(lines)
        await bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        await bot.edit_message_text(
            '📦 Choose category',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=stock_categories_list(categories, None),
        )
        return
    await call.answer('Insufficient rights')


async def view_stock_category_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    role = check_role(user_id)
    if not role & Permission.OWN:
        await call.answer('Insufficient rights')
        return
    category = call.data.split(':', 1)[1]
    subs = get_all_subcategories(category)
    if subs:
        parent = get_category_parent(category)
        await bot.edit_message_text(
            '📂 Choose category',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=stock_categories_list(subs, parent),
        )
        return
    items = get_all_item_names(category)
    if items:
        await bot.edit_message_text(
            '🏷 Choose item',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=stock_goods_list(items, category),
        )
        return
    await call.answer('No items')


async def view_stock_item_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    role = check_role(user_id)
    if not role & Permission.OWN:
        await call.answer('Insufficient rights')
        return
    _, item_name, category = call.data.split(':', 2)
    values = get_item_values(item_name)
    if values:
        await bot.edit_message_text(
            f'📦 Stock for {display_name(item_name)}',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=stock_values_list(values, item_name, category),
        )
        return
    await call.answer('No stock')


async def view_stock_value_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    role = check_role(user_id)
    if not role & Permission.OWN:
        await call.answer('Insufficient rights')
        return
    _, value_id, item_name, category = call.data.split(':', 3)
    value_id = int(value_id)
    value = get_item_value_by_id(value_id)
    if not value:
        await call.answer('Not found')
        return
    if value['value'] and os.path.isfile(value['value']):
        desc = ''
        desc_file = f"{value['value']}.txt"
        if os.path.isfile(desc_file):
            with open(desc_file) as f:
                desc = f.read()
        with open(value['value'], 'rb') as doc:
            file_lower = value['value'].lower()
            if file_lower.endswith('.mp4'):
                await bot.send_video(user_id, doc, caption=desc or None)
            elif file_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                await bot.send_photo(user_id, doc, caption=desc or None)
            else:
                await bot.send_document(user_id, doc, caption=desc or None)
    else:
        await bot.send_message(user_id, value['value'])
    await bot.edit_message_text(
        f'ID {value_id}',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=stock_value_actions(value_id, item_name, category),
    )


async def view_stock_delete_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    role = check_role(user_id)
    if not role & Permission.OWN:
        await call.answer('Insufficient rights')
        return
    _, value_id, item_name, category = call.data.split(':', 3)
    value_id = int(value_id)
    value = get_item_value_by_id(value_id)
    if value and value['value'] and os.path.isfile(value['value']):
        os.remove(value['value'])
    buy_item(value_id)
    values = get_item_values(item_name)
    await bot.edit_message_text(
        '✅ Stock deleted',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=stock_values_list(values, item_name, category),
    )


def register_view_stock(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        view_stock_callback_handler, lambda c: c.data == 'view_stock'
    )
    dp.register_callback_query_handler(
        view_stock_category_handler,
        lambda c: c.data.startswith('stock_cat:'),
        state='*',
    )
    dp.register_callback_query_handler(
        view_stock_item_handler,
        lambda c: c.data.startswith('stock_item:'),
        state='*',
    )
    dp.register_callback_query_handler(
        view_stock_value_handler,
        lambda c: c.data.startswith('stock_val:'),
        state='*',
    )
    dp.register_callback_query_handler(
        view_stock_delete_handler,
        lambda c: c.data.startswith('stock_del:'),
        state='*',
    )
