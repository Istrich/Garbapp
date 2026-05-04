# Telegram Mini App — «Помощь в утилизации»

Статическое веб-приложение для Telegram: загрузка фото + почтовый индекс → **`POST /api/v1/analyze`** (те же поля, что на вкладке «Тест по фото» в админке).

## Что нужно

1. **HTTPS** — Telegram открывает Mini App только по защищённому URL (продакшен-домен, Cloudflare Pages, Netlify, свой nginx и т.д.).
2. Публичный URL **backend API** с CORS: в `backend` для мини-приложения должен быть разрешён origin страницы Mini App (или временно `GARBAGE_CORS_ORIGINS=*` только для отладки).

## Настройка API

**Вариант A.** Параметр в ссылке, которую даёте BotFather / кнопке бота:

```text
https://your-domain.example/telegram-miniapp/index.html?api=https://api.example.com
```

**Вариант B.** В `index.html` задайте:

```html
<script>
  window.__API_BASE__ = "https://api.example.com";
</script>
```

Без слэша на конце; путь `/api/v1/analyze` добавляется в коде.

## Локальная проверка

1. Поднимите API (`docker compose --profile backend up` или uvicorn).
2. Раздайте статику Mini App локально с HTTPS (например `ngrok http 8080`) или временно задеплойте файлы из этой папки.

## Подключение к боту

1. [@BotFather](https://t.me/BotFather) → **/newapp** или настройки бота → **Mini Apps** → указать URL на **`index.html`** (с параметром `?api=...` при необходимости).
2. В меню бота добавьте кнопку с типом **Web App** и тем же URL.

## Файлы

| Файл        | Назначение              |
|------------|-------------------------|
| `index.html` | Разметка и подключение Telegram SDK |
| `styles.css` | Оформление              |
| `app.js`     | Запрос к API, превью фото |

Авторизация админ-токеном для **`/analyze`** не требуется.
