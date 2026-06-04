import os
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urljoin

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
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").strip().rstrip("/")
REQUEST_TIMEOUT_SECONDS = 20

ASK_FIELD = 1
FieldType = Literal["number", "text", "bool"]
CLEAR_HISTORY_TEXT = "🗑 Очистить историю"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    context.user_data.setdefault("answers", {})
    step_index = context.user_data.get("step_index", 0)
    if not isinstance(step_index, int) or step_index < 0 or step_index >= len(FIELD_STEPS):
        step_index = 0
        context.user_data["step_index"] = step_index
    return FIELD_STEPS[step_index]


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
    return ReplyKeyboardMarkup(
        [["/start"], [CLEAR_HISTORY_TEXT]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _predict_url() -> str:
    return urljoin(f"{API_URL}/", "predict")


def _log_exception(message: str, exc: BaseException, **extra: Any) -> None:
    logger.error(
        "%s exception=%s traceback=%s extra=%s",
        message,
        repr(exc),
        traceback.format_exc(),
        extra,
    )


def _log_api_response(response: requests.Response | None) -> None:
    if response is None:
        logger.error("API response is missing")
        return

    logger.info(
        "API response received url=%s status_code=%s response_text=%s",
        response.url,
        response.status_code,
        response.text,
    )


def _clear_user_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    context.chat_data.clear()


def _drop_persisted_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        context.application.drop_user_data(update.effective_user.id)
    if update.effective_chat:
        context.application.drop_chat_data(update.effective_chat.id)


async def _ask_current(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    step = _current_step(context)
    await update.message.reply_text(
        step.question + _skip_hint(step),
        reply_markup=_keyboard_for_step(step),
    )
    return ASK_FIELD


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Starting prediction dialog user_id=%s", update.effective_user.id if update.effective_user else None)
    _clear_user_context(context)
    context.user_data["answers"] = {}
    context.user_data["step_index"] = 0
    await update.message.reply_text(
        "Привет! Я помогу спрогнозировать цену квартиры.\n"
        "Буду задавать вопросы по одному."
    )
    return await _ask_current(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Prediction dialog cancelled user_id=%s", update.effective_user.id if update.effective_user else None)
    _clear_user_context(context)
    await update.message.reply_text(
        "Опрос остановлен. Чтобы начать заново, отправь /start.",
        reply_markup=_restart_keyboard(),
    )
    return ConversationHandler.END


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Clearing dialog history user_id=%s", update.effective_user.id if update.effective_user else None)
    _clear_user_context(context)
    _drop_persisted_context(update, context)
    await update.message.reply_text(
        "История успешно очищена.",
        reply_markup=_restart_keyboard(),
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
    logger.info(
        "Received answer user_id=%s step=%s raw=%s",
        update.effective_user.id if update.effective_user else None,
        step.name,
        text,
    )

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
    request_url = _predict_url()
    logger.info(
        "Sending prediction request user_id=%s url=%s payload=%s",
        update.effective_user.id if update.effective_user else None,
        request_url,
        payload,
    )
    await update.message.reply_text("Считаю прогноз...", reply_markup=ReplyKeyboardRemove())

    response = None
    try:
        response = requests.post(request_url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        _log_api_response(response)
        response.raise_for_status()
    except requests.HTTPError as exc:
        _log_exception(
            "API returned HTTP error",
            exc,
            url=request_url,
            payload=payload,
            status_code=response.status_code if response is not None else None,
            response_text=response.text if response is not None else None,
        )
        message = "Проверьте введённые данные и попробуйте снова."
        try:
            detail = response.json().get("detail") if response is not None else None
            if isinstance(detail, dict) and detail.get("code") == "model_unavailable":
                message = "Не удалось загрузить модель прогнозирования."
            elif response is not None and response.status_code >= 500:
                message = "Не удалось получить прогноз. Попробуйте позже."
        except ValueError as parse_exc:
            _log_exception(
                "Failed to parse API error response",
                parse_exc,
                url=request_url,
                payload=payload,
                status_code=response.status_code if response is not None else None,
                response_text=response.text if response is not None else None,
            )
            if response is not None and response.status_code >= 500:
                message = "Не удалось получить прогноз. Попробуйте позже."

        await update.message.reply_text(
            message,
            reply_markup=_restart_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END
    except requests.RequestException as exc:
        _log_exception(
            "Prediction API request failed",
            exc,
            url=request_url,
            payload=payload,
            response_text=response.text if response is not None else None,
            status_code=response.status_code if response is not None else None,
        )
        await update.message.reply_text(
            "Не удалось получить прогноз. Попробуйте позже.",
            reply_markup=_restart_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as exc:
        _log_exception(
            "Unexpected Telegram bot error while requesting prediction",
            exc,
            url=request_url,
            payload=payload,
            response_text=response.text if response is not None else None,
            status_code=response.status_code if response is not None else None,
        )
        await update.message.reply_text(
            "Не удалось получить прогноз. Попробуйте позже.",
            reply_markup=_restart_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        result = response.json()
        price = result["predicted_price_rounded"]
        currency = result.get("currency", "KZT")
    except (ValueError, KeyError, TypeError) as exc:
        _log_exception(
            "Invalid API response format",
            exc,
            url=request_url,
            payload=payload,
            status_code=response.status_code,
            response_text=response.text,
        )
        await update.message.reply_text(
            "Не удалось получить прогноз. Попробуйте позже.",
            reply_markup=_restart_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    formatted_price = f"{price:,.0f}".replace(",", " ")
    await update.message.reply_text(
        f"Прогноз цены: {formatted_price} {currency}\n\n"
        "Чтобы посчитать еще одну квартиру, нажми /start.",
        reply_markup=_restart_keyboard(),
    )
    logger.info("Prediction delivered user_id=%s result=%s", update.effective_user.id if update.effective_user else None, result)
    context.user_data.clear()
    return ConversationHandler.END


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    exc_info = None
    if context.error:
        exc_info = (type(context.error), context.error, context.error.__traceback__)
    logger.error("Unhandled Telegram error update=%s", update, exc_info=exc_info)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Не удалось получить прогноз. Попробуйте позже.",
            reply_markup=_restart_keyboard(),
        )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

    logger.info("Bot configured with API_URL=%s predict_url=%s", API_URL, _predict_url())

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("predict", start),
        ],
        states={
            ASK_FIELD: [
                CommandHandler("start", start),
                CommandHandler("predict", start),
                CommandHandler("skip", skip),
                CommandHandler("skipall", skip_all),
                MessageHandler(filters.Regex(f"^{CLEAR_HISTORY_TEXT}$"), clear_history),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_answer),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("predict", start),
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(f"^{CLEAR_HISTORY_TEXT}$"), clear_history),
        ],
        allow_reentry=True,
    )

    app.add_handler(conversation)
    app.add_handler(MessageHandler(filters.Regex(f"^{CLEAR_HISTORY_TEXT}$"), clear_history))
    app.add_error_handler(on_error)
    app.run_polling()


if __name__ == "__main__":
    main()
