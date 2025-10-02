Экспорт «Сохранённых сообщений» Telegram
========================================

Экспортирует ваши «Сохранённые сообщения» Telegram в HTML с медиа. На каждый запуск создаётся отдельная папка и ZIP-архив. Подходит для регулярных бэкапов.

Возможности
-----------
- Тёмная тема HTML
- Загрузка медиа (фото, видео, аудио, документы) с возможностью встроенного проигрывания по умолчанию
 - Фильтрация по датам (`--since`, `--until`), формат дат: DD-MM-YYYY; `--until` включительно; если указан только `--since`, верхняя граница — «сейчас»
- Ограничение размера (`--max-bytes`) для пропуска крупных файлов
- Режим прогона без скачивания медиа (`--dry-run`)
- Плашки превью для ссылок (webpage preview)
- Авто-транскрипция голосовых и круговых видео при наличии Telegram Premium (текст под спойлером)
- Отображение источника у пересланных сообщений
- Прогресс-бар в виде счётчика в одну строку (`--progress`)

Требования
----------
- Python 3.9+
- Telegram API ID/HASH с `my.telegram.org`

Установка зависимостей
----------------------
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Первый запуск (аутентификация)
------------------------------
1. Получите `api_id` и `api_hash` на `my.telegram.org`.
2. Запустите экспорт и введите телефон/код при запросе:

```bash
python main.py \
  --api-id YOUR_API_ID \
  --api-hash YOUR_API_HASH \
  --output /path/to/exports
```

- Для безвопросного запуска установите переменные окружения: `TELEGRAM_PHONE`, (одноразово `TELEGRAM_CODE`), при двухфакторной защите — `TELEGRAM_2FA_PASSWORD`. Сеанс сохранится в `saved_export.session`.

Использование
-------------
```bash
python main.py --api-id $TELEGRAM_API_ID --api-hash $TELEGRAM_API_HASH \
  --output /backups/telegram \
  [--since 29-09-2025] [--until 30-09-2025] \
  [--reverse] [--progress] \
  [--max-bytes 104857600] [--dry-run] [--lang ru|en] [--lang-file /path/to/i18n.json]
```

- `--reverse`: от старых к новым (по умолчанию — новые сверху).
- Встроенное воспроизведение видео/аудио включено по умолчанию.
- `--progress`: печатать счётчик прогресса в одну строку.
- `--max-bytes`: не скачивать файлы крупнее порога.
- `--since` / `--until`: DD-MM-YYYY; `--until` включительно; при указании только `--since` верхняя граница — «сейчас». Метки времени выводятся в локальном часовом поясе машины.
- Результат: `EXPORT_DIR/saved_messages_DDMMYYYY_HHMMSS/` с `index.html` и `media/` + ZIP.
- `--lang`: язык интерфейса экспорта (`ru` по умолчанию, `en` для английского).
- `--lang-file`: JSON-файл с переопределениями строк интерфейса.

Планировщики
------------

Cron
----
```bash
crontab -e
```
Пример (каждый день в 03:30):
```cron
30 3 * * * cd /home/bofh/Documents/sadmin.io/vibe1 && /usr/bin/bash -lc "source .venv/bin/activate && TELEGRAM_API_ID=... TELEGRAM_API_HASH=... python main.py --output /backups/telegram" >> /var/log/telegram_saved_export.log 2>&1
```

systemd
-------
Создайте `/etc/systemd/system/telegram-saved-export.service`:
```ini
[Unit]
Description=Telegram Saved Messages Export
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/bofh/Documents/sadmin.io/vibe1
Environment=TELEGRAM_API_ID=YOUR_ID
Environment=TELEGRAM_API_HASH=YOUR_HASH
ExecStart=/usr/bin/bash -lc 'source .venv/bin/activate && python main.py --output /backups/telegram'
```

Таймер `/etc/systemd/system/telegram-saved-export.timer`:
```ini
[Unit]
Description=Schedule Telegram Saved Messages Export

[Timer]
OnCalendar=03:30
Persistent=true

[Install]
WantedBy=timers.target
```

Активировать:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-saved-export.timer
```

Примечания
----------
- Соблюдайте лимиты Telegram; возможны ограничения.
- Бережно храните сессию и ключи API.
- Открывайте `index.html` локально в браузере. Встроенное воспроизведение зависит от форматов/кодеков.

— — —

Telegram Saved Messages Exporter (English)
=========================================

Exports your Telegram "Saved Messages" to a self-contained HTML + media folder, zipped per run. Intended for scheduled backups.

Features
--------
- HTML render with simple dark theme
- Media download (photos, videos, audio, documents) with optional inline playback
- Date filters (`--since`, `--until`) — DD-MM-YYYY (UTC); `--until` inclusive; if only `--since` is provided, upper bound is “now”
- Size cap (`--max-bytes`) to skip large files
- Dry run mode (no media download)
- Link previews (webpage preview)
- Auto transcription of voice/round videos with Telegram Premium (spoiler)
- Shows original author for forwarded messages
- One-line progress indicator (`--progress`)

Requirements
------------
- Python 3.9+
- Telegram API credentials from my.telegram.org

Install deps:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

First run (authentication)
--------------------------
```bash
python main.py \
  --api-id YOUR_API_ID \
  --api-hash YOUR_API_HASH \
  --output /path/to/exports
```

Usage
-----
```bash
python main.py --api-id $TELEGRAM_API_ID --api-hash $TELEGRAM_API_HASH \
  --output /backups/telegram \
  [--since 29-09-2025] [--until 30-09-2025] \
  [--reverse] [--embed-video] [--embed-audio] [--progress] \
  [--max-bytes 104857600] [--dry-run] [--lang ru|en] [--lang-file /path/to/i18n.json]
```

- `--reverse`: oldest to newest (default newest first).
- Inline video/audio playback is enabled by default.
- `--progress`: live single-line counter; shows total if available.
- `--max-bytes`: skip downloads larger than the limit.
- `--since` / `--until`: DD-MM-YYYY. `--until` inclusive. If only `--since` is set, upper bound is “now”. Timestamps are displayed in the machine's local timezone.
- Output folder `EXPORT_DIR/saved_messages_DDMMYYYY_HHMMSS/` with `index.html` and `media/`, plus a `.zip`.
- `--lang`: export UI language (`ru` default; `en` to switch).
- `--lang-file`: JSON file to override UI strings.

Scheduling
----------
See Russian section above for `cron` and `systemd` examples; paths are identical.

Notes
-----
- Respect Telegram limits; excessive scraping may be rate-limited.
- Keep your session and API credentials secure.
- Exports are local HTML; open `index.html` in a browser. Inline playback depends on file formats and codecs.
Transcription
-------------
If your account is Premium and you use `--embed-audio` or `--embed-video`, the exporter will request Telegram's built-in transcription for voice notes and round video messages and include the text under a collapsible "Transcription" spoiler. If Premium or Telegram transcription is unavailable, nothing is added.

