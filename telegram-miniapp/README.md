# Telegram Mini App — «Помощь в утилизации»

Статическое веб-приложение для Telegram: загрузка фото + почтовый индекс → **`POST /api/v1/analyze`** (те же поля, что на вкладке «Тест по фото» в админке).

В этом проекте мини-апп раздаётся самим FastAPI по URL **`/miniapp/`**.

## Что нужно

1. **HTTPS** — Telegram открывает Mini App только по защищённому URL.
2. Если мини-апп и API на одном домене (вариант Railway по умолчанию), CORS настраивать отдельно обычно не нужно.

## Настройка API

**Вариант A (рекомендуется, same-origin).**

Просто давайте в BotFather ссылку на:

```text
https://<railway-domain>/miniapp/
```

Код возьмёт API как `window.location.origin`.

**Вариант B.** Явный API-параметр в ссылке:

```text
https://your-domain.example/telegram-miniapp/index.html?api=https://api.example.com
```

**Вариант C.** В `index.html` задайте:

```html
<script>
  window.__API_BASE__ = "https://api.example.com";
</script>
```

Без слэша на конце; путь `/api/v1/analyze` добавляется в коде.

## Локальная проверка

1. Поднимите API (`docker compose --profile backend up` или uvicorn).
2. Откройте `http://localhost:8000/miniapp/` (локально) или публичный HTTPS URL после деплоя.

## Подключение к боту

1. [@BotFather](https://t.me/BotFather) → **/newapp** или настройки бота → **Mini Apps** → указать URL **`https://<railway-domain>/miniapp/`**.
2. В меню бота добавьте кнопку с типом **Web App** и тем же URL.

## Файлы

| Файл        | Назначение              |
|------------|-------------------------|
| `index.html` | Разметка и подключение Telegram SDK |
| `styles.css` | Оформление              |
| `app.js`     | Запрос к API, превью фото |

Авторизация админ-токеном для **`/analyze`** не требуется.
