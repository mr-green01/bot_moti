from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import aiosqlite
import asyncio

class SchedulerTasks:
    def __init__(self, bot):
        self.bot = bot  # Передаём ссылку на экземпляр бота для отправки сообщений
        self.scheduler = AsyncIOScheduler()

    def start(self):
        # Планирование задач
        self.scheduler.add_job(
            self.send_reminder, IntervalTrigger(hours=24), id='habit_reminder', replace_existing=True
        )
        self.scheduler.add_job(
            self.update_progress, IntervalTrigger(hours=1), id='progress_update', replace_existing=True
        )
        self.scheduler.start()

    async def update_progress(self):
        try:
            async with aiosqlite.connect('grim_hustle.db') as conn:
                async with conn.execute(
                    'SELECT id, habit_name, progress, total, frequency FROM habits WHERE archived = 0'
                ) as cursor:
                    habits = await cursor.fetchall()

                for habit in habits:
                    habit_id, habit_name, progress, total, frequency = habit
                    increment = self._calculate_increment(frequency, total)
                    new_progress = progress + increment

                    if new_progress >= total:
                        await conn.execute(
                            'UPDATE habits SET progress = ?, archived = 1 WHERE id = ?',
                            (total, habit_id)
                        )
                    else:
                        await conn.execute(
                            'UPDATE habits SET progress = ? WHERE id = ?',
                            (new_progress, habit_id)
                        )
                await conn.commit()
        except aiosqlite.Error as e:
            print(f"Ошибка базы данных при обновлении прогресса: {e}")

    async def send_reminder(self):
        try:
            async with aiosqlite.connect('grim_hustle.db') as conn:
                async with conn.execute(
                    'SELECT user_id, habit_name, frequency FROM habits WHERE archived = 0'
                ) as cursor:
                    habits = await cursor.fetchall()

                for user_id, habit_name, frequency in habits:
                    if self.should_send_reminder(frequency):
                        message = f"📌 Напоминание: не забывай про свою привычку '{habit_name}'! Ты на правильном пути к успеху 💪"
                        try:
                            await self.bot.send_message(user_id, message)
                        except Exception as e:
                            print(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
        except Exception as e:
            print(f"Ошибка отправки напоминаний: {e}")

    def _calculate_increment(self, frequency, total):
        if frequency == 'Ежедневно':
            return (100 / 30) / 24
        elif frequency == 'Еженедельно':
            return (100 / 4) / 168
        elif frequency == 'Ежемесячно':
            return 100 / 720
        return 0

    def should_send_reminder(self, frequency):
        now = datetime.now()
        if frequency == 'Ежедневно':
            return True
        elif frequency == 'Еженедельно':
            return now.weekday() == 0
        elif frequency == 'Ежемесячно':
            return now.day == 1
        return True
