import os
from dataclasses import dataclass
from typing import Any, Literal

import requests
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

ASK_FIELD = 1
FieldType = Literal["number", "text", "bool"]


@dataclass(frozen=True)
class FieldStep:
    name: str
    question: str
    field_type: FieldType
    required: bool = False
    options: tuple[str, ...] = ()


FIELD_STEPS = [
    FieldStep("rooms", "Сколько комнат? Например: 2", "number", True),
    FieldStep("area", "Общая площадь в м²? Например: 55", "number", True),
    FieldStep("floor", "Этаж квартиры? Например: 5", "number", True),
    FieldStep("total_floors", "Сколько всего этажей в доме? Например: 12", "number", True),
    FieldStep("living_area", "Жилая площадь в м²? Например: 32", "number"),
    FieldStep("kitchen_area", "Площадь кухни в м²? Например: 10", "number"),
    FieldStep(
        "house_type",
        "Тип дома? Выбери вариант или напиши свой.",
        "text",
        options=("монолитный", "кирпичный", "панельный", "иное"),
    ),
    FieldStep("year_built", "Год постройки? Например: 2018", "number"),
    FieldStep("ceiling_height", "Высота потолков? Например: 2.7", "number"),
    FieldStep(
        "condition",
        "Состояние? Выбери вариант или напиши свой.",
        "text",
        options=("хорошее", "среднее", "требует ремонта", "черновая отделка"),
    ),
    FieldStep(
        "bathroom",
        "Санузел? Выбери вариант или напиши свой.",
        "text",
        options=("раздельный", "совмещенный", "2 санузла", "нет"),
    ),
    FieldStep(
        "floor_type",
        "Тип пола? Выбери вариант или напиши свой.",
        "text",
        options=("ламинат", "паркет", "линолеум", "плитка", "черновой"),
    ),
    FieldStep(
        "district",
        "Район? Выбери вариант или напиши свой.",
        "text",
        options=("Есильский р-н", "Алматинский р-н", "Сарыаркинский р-н", "Байконур р-н"),
    ),
    FieldStep("latitude", "Широта? Например: 51.128", "number"),
    FieldStep("longitude", "Долгота? Например: 71.43", "number"),
    FieldStep("has_balcony", "Есть балкон? Ответь: да или нет", "bool"),
    FieldStep("has_parking", "Есть парковка? Ответь: да или нет", "bool"),
    FieldStep("has_furniture", "Есть мебель? Ответь: да или нет", "bool"),
    FieldStep("has_security", "Есть охрана? Ответь: да или нет", "bool"),
]


def _current_step(context: ContextTypes.DEFAULT_TYPE) -> FieldStep:
    return FIELD_STEPS[context.user_data["step_index"]]


def _keyboard_for_step(step: FieldStep) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    buttons = []

    if step.field_type == "bool":
        buttons.append(["да", "нет"])
    elif step.options:
        buttons.extend([list(step.options[i : i + 2]) for i in range(0, len(step.options), 2)])

    if not step.required:
        buttons.append(["Пропустить"])

    if not buttons:
        return ReplyKeyboardRemove()

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)


def _skip_hint(step: FieldStep) -> str:
    if step.required:
        return ""
    return "\n\nЕсли не знаешь, нажми Пропустить или отправь /skip."


def _restart_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["/start"]], resize_keyboard=True, one_time_keyboard=True)


async def _ask_current(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    step = _current_step(context)
    await update.message.reply_text(
        step.question + _skip_hint(step),
        reply_markup=_keyboard_for_step(step),
    )
    return ASK_FIELD


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["answers"] = {}
    context.user_data["step_index"] = 0
    await update.message.reply_text(
        "Привет! Я помогу спрогнозировать цену квартиры.\n"
        "Буду задавать вопросы по одному."
    )
    return await _ask_current(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Опрос остановлен. Чтобы начать заново, отправь /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def _parse_answer(text: str, step: FieldStep) -> Any:
    value = text.strip()

    if step.field_type == "number":
        return float(value.replace(",", "."))

    if step.field_type == "bool":
        normalized = value.lower()
        if normalized in {"да", "yes", "y", "true", "1", "+"}:
            return True
        if normalized in {"нет", "no", "n", "false", "0", "-"}:
            return False
        raise ValueError("Введите да или нет.")

    return value


async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    step = _current_step(context)

    if step.required:
        await update.message.reply_text("Это обязательное поле, его нельзя пропустить.")
        return await _ask_current(update, context)

    context.user_data["answers"][step.name] = None
    context.user_data["step_index"] += 1
    return await _next_or_predict(update, context)


async def skip_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    while context.user_data["step_index"] < len(FIELD_STEPS):
        step = _current_step(context)
        if step.required:
            await update.message.reply_text("Сначала нужно ответить на обязательный вопрос.")
            return await _ask_current(update, context)

        context.user_data["answers"][step.name] = None
        context.user_data["step_index"] += 1

    return await _next_or_predict(update, context)


async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    step = _current_step(context)
    text = update.message.text or ""

    if text.strip().lower() == "пропустить":
        return await skip(update, context)

    if text.strip().lower() in {"пропустить все", "skip all", "skipall"}:
        return await skip_all(update, context)

    try:
        value = _parse_answer(text, step)
    except ValueError:
        await update.message.reply_text("Не получилось распознать ответ. Попробуй еще раз.")
        return await _ask_current(update, context)

    context.user_data["answers"][step.name] = value
    context.user_data["step_index"] += 1
    return await _next_or_predict(update, context)


async def _next_or_predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data["step_index"] < len(FIELD_STEPS):
        return await _ask_current(update, context)

    payload = {
        key: value
        for key, value in context.user_data["answers"].items()
        if value is not None
    }
    await update.message.reply_text("Считаю прогноз...", reply_markup=ReplyKeyboardRemove())

    try:
        response = requests.post(f"{API_URL}/predict", json=payload, timeout=20)
        response.raise_for_status()
    except requests.HTTPError as exc:
        details = ""
        try:
            api_errors = response.json().get("detail", [])
            if api_errors:
                details = "\n\nДетали:\n" + "\n".join(
                    f"- {'.'.join(map(str, error.get('loc', [])))}: {error.get('msg')}"
                    for error in api_errors
                )
        except ValueError:
            details = f"\n\nОтвет API: {response.text}"

        await update.message.reply_text(
            "API получил данные, но не смог их обработать."
            f"{details}\n\n"
            "Попробуй начать заново: /start"
        )
        return ConversationHandler.END
    except requests.RequestException as exc:
        await update.message.reply_text(
            "Не смог получить прогноз от API. "
            "Проверь, что backend запущен командой:\n"
            "uvicorn backend.main:app --reload\n\n"
            f"Ошибка: {exc}"
        )
        return ConversationHandler.END

    result = response.json()
    price = result["predicted_price_rounded"]
    currency = result.get("currency", "KZT")
    formatted_price = f"{price:,.0f}".replace(",", " ")
    await update.message.reply_text(
        f"Прогноз цены: {formatted_price} {currency}\n\n"
        "Чтобы посчитать еще одну квартиру, нажми /start.",
        reply_markup=_restart_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("predict", start),
        ],
        states={
            ASK_FIELD: [
                CommandHandler("skip", skip),
                CommandHandler("skipall", skip_all),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_answer),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conversation)
    app.run_polling()


if __name__ == "__main__":
    main()
