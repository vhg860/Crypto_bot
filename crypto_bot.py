import logging
import requests

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters)

COINMARKETCAP_API_KEY = ''
TELEGRAM_BOT_TOKEN = ''
BASE_URL = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

user_thresholds = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.
    Отправляет приветственное сообщение и инструкции пользователю.
    """
    user = update.effective_user
    reply_keyboard = [['/set', '/cancel', '/price']]
    await update.message.reply_text(
        f'Привет, {user.first_name}! Я бот для отслеживания '
        'курса криптовалют.\n'
        'Используйте /set "криптовалюта" "мин_цена" и "макс_цена", '
        'чтобы установить порог.\n'
        'Используйте /cancel "криптовалюта", чтобы отменить '
        'отслеживание.\n'
        'Используйте /price "криптовалюта", чтобы узнать текущую '
        'стоимость.',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                         one_time_keyboard=True)
    )


async def set_threshold(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /set.
    Устанавливает пороговые значения для отслеживания криптовалюты.
    """
    try:
        symbol = context.args[0].upper()
        min_price = float(context.args[1])
        max_price = float(context.args[2])
        user_id = update.effective_user.id

        if user_id not in user_thresholds:
            user_thresholds[user_id] = []

        user_thresholds[user_id].append((symbol, min_price, max_price))
        await update.message.reply_text(
            f'Порог установлен для {symbol} в диапазоне от '
            f'${min_price} до ${max_price}.'
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Использование: /set криптовалюта "мин_цена" и "макс_цена"'
        )


async def cancel_threshold(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /cancel.
    Отменяет отслеживание указанной криптовалюты.
    """
    try:
        symbol = context.args[0].upper()
        user_id = update.effective_user.id

        if user_id in user_thresholds:
            user_thresholds[user_id] = [
                t for t in user_thresholds[user_id] if t[0] != symbol
            ]
            await update.message.reply_text(
                f'Отслеживание для {symbol} отменено.'
            )
        else:
            await update.message.reply_text(
                f'Вы не отслеживаете курс {symbol}.'
            )
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Использование: /cancel криптовалюта'
        )


def get_crypto_price(symbol: str) -> float:
    """Получает текущую цену криптовалюты от API CoinMarketCap."""
    headers = {'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY}
    params = {'symbol': symbol, 'convert': 'USD'}
    response = requests.get(BASE_URL, headers=headers, params=params)
    data = response.json()
    return data['data'][symbol]['quote']['USD']['price']


async def check_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодически проверяет цены криптовалют и отправляет уведомления."""
    for user_id, thresholds in user_thresholds.items():
        for symbol, min_price, max_price in thresholds:
            try:
                current_price = get_crypto_price(symbol)
                if current_price <= min_price or current_price >= max_price:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f'Предупреждение о цене {symbol}! '
                             f'Текущая цена: ${current_price}'
                    )
            except Exception as e:
                logger.error(f'Ошибка при получении цены для {symbol}: {e}')


async def get_price(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /price.
    Отправляет текущую цену запрошенной криптовалюты.
    """
    try:
        symbol = context.args[0].upper()
        current_price = get_crypto_price(symbol)
        await update.message.reply_text(
            f'Текущая цена {symbol}: ${current_price}'
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            'Использование: /price криптовалюта'
        )
    except Exception as e:
        await update.message.reply_text(
            f'Ошибка при получении цены для {symbol}: {e}'
        )


async def log_update(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует все полученные обновления."""
    logger.info(f"Получено обновление: {update}")


def main() -> None:
    """Функция для запуска бота."""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_threshold))
    application.add_handler(CommandHandler("cancel", cancel_threshold))
    application.add_handler(CommandHandler("price", get_price))
    application.add_handler(MessageHandler(filters.ALL, log_update))

    application.job_queue.run_repeating(check_prices, interval=60)

    application.run_polling()


if __name__ == '__main__':
    main()
