# Tester — Phase 1 data pipeline

## Что проверено

1. **`scripts/process_zip_codes.py`** — успешный прогон на полном `Index base/KEN_ALL_ROME.CSV`, кодировка `shift_jis`, без ошибок декодирования.
2. **SQLite** — запрос  
   `SELECT district_id FROM zip_mapping WHERE zip_code = '1600022'` возвращает **`shinjuku`**.
3. **Строк обработано:** 124788 (соответствует объёму CSV).
4. **`scripts/extract_shinjuku_pdf.py --fetch`** — загрузка PDF и генерация черновика в `knowledge/generated/` (после установки `requirements-data.txt`).

## Воспроизведение

```powershell
cd "f:\Garbaje app"
python scripts/process_zip_codes.py
python -c "import sqlite3; c=sqlite3.connect('data/zip_codes.db'); print(c.execute(\"SELECT district_id FROM zip_mapping WHERE zip_code='1600022'\").fetchone())"
pip install -r requirements-data.txt
python scripts/extract_shinjuku_pdf.py --fetch
```

## Ручная проверка контента

- Открыть `knowledge/shinjuku_rules.md` и убедиться, что раздел **Resources (Plastic)** содержит условие **30 см / 5 мм / 100% пластик** и упоминание **апреля 2024**.
