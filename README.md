# Astana Apartment Price API

FastAPI backend for predicting apartment prices with `randomforest_log_target.pkl`.

## Run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Swagger docs:

```text
http://127.0.0.1:8000/docs
```

## Prediction Request

Telegram bot can send a POST request to:

```text
http://127.0.0.1:8000/predict
```

Example JSON:

```json
{
  "rooms": 2,
  "area": 55,
  "living_area": 32,
  "kitchen_area": 10,
  "floor": 5,
  "total_floors": 12,
  "house_type": "монолитный",
  "year_built": 2018,
  "ceiling_height": 2.7,
  "condition": "хорошее",
  "bathroom": "раздельный",
  "floor_type": "ламинат",
  "district": "Есильский р-н",
  "latitude": 51.128,
  "longitude": 71.430,
  "has_balcony": true,
  "has_parking": false,
  "has_furniture": true,
  "has_security": true
}
```

## Telegram Bot

Create `.env` from `.env.example` and put your bot token there:

```text
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
API_URL=http://127.0.0.1:8000
```

Run backend in one terminal:

```bash
uvicorn backend.main:app --reload
```

Run bot in another terminal:

```bash
python bot/bot.py
```

In Telegram send:

```text
/start
```
