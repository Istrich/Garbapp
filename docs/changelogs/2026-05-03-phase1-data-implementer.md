# Change log — Phase 1 (data pipeline)

## Что сделано

- Добавлен пакет `garbage_data`: нормализация ромадзи муниципалитета → `district_id`, обёртка PyMuPDF4LLM для PDF.
- Скрипт `scripts/process_zip_codes.py`: чтение `KEN_ALL_ROME.CSV` в кодировке `shift_jis`, запись SQLite `data/zip_codes.db`, таблица `zip_mapping`, индекс по `zip_code`.
- Скрипт `scripts/extract_shinjuku_pdf.py`: загрузка официального `000378895.pdf` и генерация черновика Markdown в `knowledge/generated/`.
- Файл `knowledge/shinjuku_rules.md`: структурированная база для RAG с акцентом на правило апреля 2024 (製品プラスチック).

## Почему

Соответствие `PHASE_1_DATA.md` и `.cursorrules`: маппинг индексов для последующего Redis/Qdrant и контент правил для эмбеддингов.

## Как проверить

```powershell
cd "f:\Garbaje app"
python scripts/process_zip_codes.py
sqlite3 data/zip_codes.db "SELECT district_id FROM zip_mapping WHERE zip_code='1600022';"
pip install -r requirements-data.txt
python scripts/extract_shinjuku_pdf.py --fetch
```
