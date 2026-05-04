🗑️ AI Waste Classifier: Tech Stack (Japan Edition)
Данный стек выбран для обеспечения максимальной скорости разработки (Time-to-Market) и бесшовной интеграции с современными AI-инструментами.

📱 Mobile (iOS & Android)
Framework: Flutter (Dart)

Почему: Единая кодовая база для обеих платформ, высокая производительность и отличная поддержка библиотек для работы с камерой.

State Management: Riverpod или Bloc

Почему: Надежное управление состоянием приложения при сложных асинхронных запросах к ИИ.

⚙️ Backend (API & Logic)
Language: Python 3.11+

Почему: Родной язык для AI/ML, огромный выбор библиотек для обработки данных.

Framework: FastAPI

Почему: Самый быстрый асинхронный фреймворк на Python. Автоматическая генерация документации Swagger для фронтенда.

AI Orchestration: LangChain

Почему: Удобное управление цепочками промптов (Chained Prompts) и RAG-логикой.

🧠 AI & Data Processing
LLM (Vision & Reasoning): OpenAI GPT-4o (через API)

Почему: Лучшее на текущий момент понимание изображений и контекста.

Vector Database (RAG): Qdrant или ChromaDB

Почему: Qdrant отлично подходит для продакшена и легко фильтрует данные по метаданным (например, по названию района).

Embeddings: OpenAI text-embedding-3-small

Почему: Дешевые и качественные векторы для индексации инструкций.

🗄️ Storage (Databases)
Primary DB: PostgreSQL

Задачи: Хранение профилей пользователей, их почтовых индексов и истории запросов.

Cache / Key-Value: Redis

Задачи: Кэширование маппинга «Индекс -> Район» для мгновенного ответа.

Object Storage: AWS S3 (или аналог)

Задачи: Временное хранение фотографий мусора для анализа.

🛠️ Infrastructure & DevOps
Containerization: Docker & Docker Compose

Почему: Гарантия того, что бэкенд запустится на любом сервере.

CI/CD: GitHub Actions

Почему: Автоматическое тестирование и деплой.

API Gateway / Web Server: Nginx

Почему: Стандарт для защиты и балансировки нагрузки бэкенда.

📊 Data Preparation (Manual/Automated)
Parsing: Pandas (для обработки KEN_ALL_ROME.CSV)

PDF Extraction: PyMuPDF4LLM или Marker (для перевода PDF-инструкций мэрий в Markdown для RAG)

Архитектурная схема потока данных:
App (Flutter) ➔ Отправляет ZIP_CODE ➔ Backend (FastAPI).

Backend ➔ Проверяет Redis/Postgres ➔ Возвращает DISTRICT_ID.

App ➔ Отправляет Photo ➔ Backend.

Backend ➔ RAG (Qdrant) ➔ Извлекает правила для DISTRICT_ID.

Backend ➔ AI (GPT-4o) ➔ Запрос 1 (Описание фото) + Запрос 2 (Вердикт на базе правил).

Backend ➔ Возвращает финальный ответ ➔ App.