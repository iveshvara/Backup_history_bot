from aiogram import Bot
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from settings import TOKEN
import sqlite3
import asyncio
import aioschedule

bot = Bot(TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

connect = sqlite3.connect('base.db')
cursor = connect.cursor()


class EnteringTask(StatesGroup):
    id_task = ''
    callback = ''
    part = State()


async def on_startup(_):
    connect.execute('CREATE TABLE IF NOT EXISTS tasks(\
        id_task INTEGER, id_user INTEGER, path TEXT, PRIMARY KEY("id_task" AUTOINCREMENT))')
    connect.commit()
    asyncio.create_task(scheduler())


async def scheduler():
    aioschedule.every().day.at("00:00").do(send_backup_file)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def send_backup_file():
    cursor.execute("SELECT id_user, path FROM tasks")
    records = cursor.fetchall()
    for i in records:
        await bot.send_message(i[0], i[1] + ':')
        try:
            await bot.send_document(i[0], open(i[1], 'rb'))
        except:
            await bot.send_message(i[0], "file not found")


@dp.message_handler(commands=['start', 'menu'])
async def command_start(message: types.Message):
    await menu(message, True)


@dp.message_handler(commands=['send'])
async def command_send(message: types.Message):
    await send_backup_file()


@dp.callback_query_handler(text='cancel')
async def cancel_entering_task(callback: types.CallbackQuery):
    await menu(callback)


async def menu(callback_or_message, new_message=False):
    if new_message:
        id_user = callback_or_message.chat.id
    else:
        id_user = callback_or_message.from_user.id
    cursor.execute("SELECT id_task, path FROM tasks WHERE id_user = ?", (id_user,))
    records = cursor.fetchall()

    if records is None:
        text = 'No tasks yet'
    else:
        text = 'Current tasks:'
        for i in records:
            text = text + '\n' + i[1]

    inline_kb = InlineKeyboardMarkup(row_width=1)
    inline_kb.add(InlineKeyboardButton(text='Add a task', callback_data='Add a task'))
    inline_kb.add(InlineKeyboardButton(text='Delete a task', callback_data='Delete a task'))
    if new_message:
        await callback_or_message.answer(text, reply_markup=inline_kb)
    else:
        await callback_or_message.message.edit_text(text, reply_markup=inline_kb)


@dp.callback_query_handler(text='Add a task')
async def add_a_task(callback: types.CallbackQuery):
    cursor.execute('INSERT INTO tasks (id_user) VALUES (?)', (callback.from_user.id,))
    connect.commit()

    result = connect.execute("SELECT id_task FROM tasks ORDER BY id_task DESC LIMIT 1")
    records = result.fetchone()
    EnteringTask.id_task = records[0]

    await EnteringTask.part.set()
    EnteringTask.callback = callback
    inline_kb = InlineKeyboardMarkup(row_width=1)
    inline_kb.add(InlineKeyboardButton(text='<cancel>', callback_data='cancel'))
    await callback.message.edit_text('Send the file path for backup:', reply_markup=inline_kb)


@dp.callback_query_handler(text='cancel', state=EnteringTask)
async def cancel_entering_task(callback: types.CallbackQuery, state: EnteringTask):
    cursor.execute('DELETE FROM tasks WHERE id_user=? AND path IS NULL', (callback.from_user.id,))
    connect.commit()
    await state.finish()
    await callback.message.delete()
    await menu(callback.message, True)


@dp.message_handler(state=EnteringTask.part)
async def part_is_input(message: types.Message, state: EnteringTask):
    if message.text.__len__() > 10:
        cursor.execute('UPDATE tasks SET path = ? where id_user = ? AND id_task = ?',
                       (message.text, message.from_user.id, EnteringTask.id_task))
        connect.commit()
        await message.delete()
        await menu(EnteringTask.callback)
    else:
        cursor.execute('DELETE FROM tasks WHERE id_user=? AND path IS NULL', (message.from_user.id,))
        connect.commit()
        await state.finish()
        await message.delete()
        await menu(EnteringTask.callback)


@dp.callback_query_handler(text='Delete a task')
async def delete_a_task(callback: types.CallbackQuery):
    cursor.execute("SELECT id_task, path FROM tasks WHERE id_user = ?", (callback.from_user.id,))
    records = cursor.fetchall()
    inline_kb = InlineKeyboardMarkup(row_width=1)

    if records is None or records.__len__() == 0:
        text = 'No tasks yet'
    else:
        text = 'By clicking on the button, the task will be deleted:'
        for i in records:
            inline_kb.add(InlineKeyboardButton(text=i[1], callback_data='Delete a task ' + str(i[0])))

    inline_kb.add(InlineKeyboardButton(text='<cancel>', callback_data='cancel'))
    await callback.message.edit_text(text, reply_markup=inline_kb)


@dp.callback_query_handler(lambda x: x.data and x.data.startswith('Delete a task '))
async def confirm_delete_store(callback: types.CallbackQuery):
    id_task = callback.data.replace('Delete a task ', '')
    cursor.execute('DELETE FROM tasks WHERE id_task=?', (id_task,))
    connect.commit()
    await delete_a_task(callback)


@dp.message_handler()
async def command_start(message):
    await message.delete()


executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
