import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackContext, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import sqlite3
import random
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import motivations

ADDING_HABIT, SETTING_FREQUENCY, CONFIRMING_COMPLETION = range(3)

class HabitTrackerBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self._init_db()
        self._add_archived_column()

        # Создаем планировщик
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        # Добавляем задачу на отправку уведомлений
        self.scheduler.add_job(
            self.send_reminder_sync,
            IntervalTrigger(hours=24),
            id='habit_reminder',
            replace_existing=True
        )

        # Добавляем обработчики команд и состояний
        self.conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start),
                CallbackQueryHandler(self.button_handler)
            ],
            states={
                ADDING_HABIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_habit)],
                SETTING_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_frequency)],
                CONFIRMING_COMPLETION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.complete_habit)]
            },
            fallbacks=[CommandHandler('start', self.start)]
        )

        self.app.add_handler(self.conv_handler)
        self.app.add_handler(CallbackQueryHandler(self.button_handler))

    def _init_db(self):
        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                habit_name TEXT,
                frequency TEXT,
                progress INTEGER DEFAULT 0,
                total INTEGER,
                start_date TEXT,
                archived INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
        
    def _add_archived_column(self):
        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        try:
            cursor.execute('ALTER TABLE habits ADD COLUMN archived INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    async def start(self, update: Update, context: CallbackContext):
        keyboard = [[InlineKeyboardButton("Перейти в меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(
                "Добро пожаловать в Iron Discipline! Это твой наставник на пути к дисциплине и новым привычкам. "
                "Готов начать свой путь к лучшей версии себя? Нажми Перейти в меню и начни прямо сейчас!",
                reply_markup=reply_markup
            )
        elif update.callback_query:
            await update.callback_query.message.edit_text(
                "Добро пожаловать в Iron Discipline! Это твой наставник на пути к дисциплине и новым привычкам. "
                "Готов начать свой путь к лучшей версии себя? Нажми Перейти в меню и начни прямо сейчас!",
                reply_markup=reply_markup
            )
        return ConversationHandler.END

    async def send_main_menu(self, update: Update):
        keyboard = [
            [InlineKeyboardButton("Добавить привычку", callback_data='add_habit')],
            [InlineKeyboardButton("Показать прогресс", callback_data='progress')],
            [InlineKeyboardButton("Получить мотивацию", callback_data='motivation')],
            [InlineKeyboardButton("Удалить привычку", callback_data='complete_habit')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            "Ты готов улучшить себя? Отлично! Вот что мы можем сделать вместе:\n\n"
            "🌱 Добавить привычку: Напиши свою новую цель, выбери, как часто будешь её выполнять, и мы начнём путь!\n\n"
            "🚀 Показать прогресс: Загляни в свои достижения и посмотри, как продвигаешься. Каждый шаг — это маленькая победа!\n\n"
            "💪 Получить мотивацию: Иногда нужно немного силы и вдохновения. Получи фразу, которая поднимет боевой дух!\n\n"
            "🎯 Завершить привычку: Как только ты освоил привычку — можно удалить её.\n\n"
            "Выбирай цель, ставь план и побеждай себя каждый день! 🌟",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        if query.data == 'main_menu':
            await self.send_main_menu(update)
            return ConversationHandler.END
        elif query.data == 'add_habit':
            await query.edit_message_text("Введите название привычки:")
            return ADDING_HABIT
        elif query.data == 'progress':
            await self.check_progress(update, context)
            return ConversationHandler.END
        elif query.data == 'motivation':
            await self.send_motivation(update, context)
            return ConversationHandler.END
        elif query.data == 'complete_habit':
            await query.edit_message_text("Введите название привычки, которую хотите удалить:")
            return CONFIRMING_COMPLETION

    async def add_habit(self, update: Update, context: CallbackContext):
        habit_name = update.message.text
        context.user_data['habit_name'] = habit_name

        keyboard = [
            [KeyboardButton("Ежедневно")],
            [KeyboardButton("Еженедельно")],
            [KeyboardButton("Ежемесячно")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Как часто вы хотите выполнять эту привычку?", reply_markup=reply_markup)
        return SETTING_FREQUENCY

    async def set_frequency(self, update: Update, context: CallbackContext):
        frequency = update.message.text
        habit_name = context.user_data.get('habit_name')
        user_id = update.message.from_user.id

        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO habits (user_id, habit_name, frequency, total, start_date) VALUES (?, ?, ?, ?, ?)',
                      (user_id, habit_name, frequency, 30, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"Привычка '{habit_name}' добавлена с частотой '{frequency}'. Удачи!")
        keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Вы можете вернуться в главное меню и продолжить отслеживание!", reply_markup=reply_markup)
        return ConversationHandler.END

    async def complete_habit(self, update: Update, context: CallbackContext):
        habit_name = update.message.text
        user_id = update.message.from_user.id

        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE habits SET archived = 1 WHERE user_id = ? AND habit_name = ?', (user_id, habit_name))
        affected_rows = cursor.rowcount
        conn.commit()
        conn.close()

        if affected_rows > 0:
            message = f"Привычка '{habit_name}' успешно удалена!"
        else:
            message = f"Привычка '{habit_name}' не найдена."

        keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)
        return ConversationHandler.END

    async def check_progress(self, update: Update, context: CallbackContext):
        query = update.callback_query
        user_id = query.from_user.id

        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        cursor.execute('SELECT habit_name, progress, total FROM habits WHERE user_id = ? AND archived = 0', (user_id,))
        habits = cursor.fetchall()
        conn.close()

        if not habits:
            message = "У вас пока нет активных привычек. Начните с добавления новой привычки!"
        else:
            message = "Ваш прогресс:\n\n"
            for habit in habits:
                name, progress, total = habit
                percentage = (progress / total) * 100 if total > 0 else 0
                message += f"🎯 {name}: {progress}/{total} ({percentage:.1f}%)\n"

        keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def send_motivation(self, update: Update, context: CallbackContext):
        motivational_quotes = motivations.motivations_list
        query = update.callback_query
        quote = random.choice(motivational_quotes)
        keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"💪 {quote}", reply_markup=reply_markup)

    async def send_reminder(self):
        conn = sqlite3.connect('grim_hustle.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, habit_name, frequency FROM habits WHERE archived = 0')
        habits = cursor.fetchall()
        conn.close()

        for user_id, habit_name, frequency in habits:
            message = f"Не забывай про свою привычку '{habit_name}'! Продолжай работать над собой!"
            await self.app.bot.send_message(user_id, message)

    def send_reminder_sync(self):
        asyncio.run(self.send_reminder())

    def run(self):
        self.app.run_polling()

# Запуск бота
if __name__ == "__main__":
    bot = HabitTrackerBot('7553618991:AAF9_O2JYaLbwbFRuMmXURk5wfJv9McViPY')
    bot.run()

