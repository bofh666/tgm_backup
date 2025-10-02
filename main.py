#!/usr/bin/env python3
import asyncio
import os
import sys
import html
import json
import re
import argparse
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from telethon.tl import functions as tl_functions
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo


CSS_STYLE = """
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, Helvetica, "Apple Color Emoji", "Segoe UI Emoji"; margin: 0; background: #0f1115; color: #e6e6e6; }
.container { max-width: 900px; margin: 0 auto; padding: 24px; }
.header { position: sticky; top: 0; background: #0f1115; padding: 16px 24px; border-bottom: 1px solid #1e212a; z-index: 10; }
.title { margin: 0; font-size: 20px; }
.meta { color: #a2a2a2; font-size: 12px; margin-top: 4px; }
.message { padding: 16px; border-bottom: 1px solid #1e212a; }
.msg-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.msg-id { color: #6fa8ff; font-weight: 600; font-size: 12px; }
.msg-date { color: #9aa4b2; font-size: 12px; white-space: nowrap; }
.msg-text { margin-top: 8px; line-height: 1.55; word-wrap: break-word; }
.msg-text a { color: #8ab4ff; text-decoration: none; border-bottom: 1px dashed #8ab4ff33; }
.msg-text a:hover { border-bottom-color: #8ab4ff; }
.media { margin-top: 12px; }
img.media-img { max-width: 100%; height: auto; border-radius: 8px; border: 1px solid #232735; }
video.media-vid, audio.media-aud { max-width: 100%; display: block; }
.file-link { display: inline-flex; align-items: center; gap: 8px; color: #d2d2d2; }
.badge { font-size: 10px; padding: 2px 6px; border: 1px solid #333a4a; border-radius: 6px; color: #9aa4b2; }
code { background: #1a1f2b; border: 1px solid #232735; padding: 1px 4px; border-radius: 4px; }
pre { background: #1a1f2b; border: 1px solid #232735; padding: 12px; border-radius: 8px; overflow: auto; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; max-width: 100%; }
.msg-fwd { margin-top: 6px; color: #a6b0bf; font-size: 12px; }
.link-preview { margin-top: 12px; border: 1px solid #232735; border-radius: 10px; overflow: hidden; display: grid; grid-template-columns: 160px 1fr; background: #131725; }
.link-preview .thumb { background: #0f1115; border-right: 1px solid #232735; }
.link-preview .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.link-preview .meta { padding: 12px; }
.link-preview .site { color: #9aa4b2; font-size: 12px; margin-bottom: 6px; }
.link-preview .title { color: #e6e6e6; font-weight: 600; margin: 0 0 6px 0; font-size: 14px; }
.link-preview .desc { color: #c9d1d9; font-size: 12px; line-height: 1.4; }
.link-preview a { color: #8ab4ff; text-decoration: none; }
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Telegram Saved Messages to HTML with media.")
    parser.add_argument("--api-id", type=int, default=int(os.environ.get("TELEGRAM_API_ID", "0")), help="Telegram API ID (from my.telegram.org)")
    parser.add_argument("--api-hash", type=str, default=os.environ.get("TELEGRAM_API_HASH", ""), help="Telegram API Hash (from my.telegram.org)")
    parser.add_argument("--session", type=str, default=os.environ.get("TELEGRAM_SESSION", "saved_export"), help="Session file name or StringSession value")
    parser.add_argument("--output", type=str, default=os.environ.get("EXPORT_DIR", "./exports"), help="Output directory for exports")
    parser.add_argument("--since", type=str, default=os.environ.get("EXPORT_SINCE", ""), help="Date DD-MM-YYYY (UTC) to include messages on/after this date")
    parser.add_argument("--until", type=str, default=os.environ.get("EXPORT_UNTIL", ""), help="Date DD-MM-YYYY (UTC) to include messages on/before this date")
    parser.add_argument("--reverse", action="store_true", help="Render in oldest-to-newest order (default shows newest first)")
    parser.add_argument("--max-bytes", type=int, default=int(os.environ.get("EXPORT_MAX_BYTES", "0")), help="Skip downloading files larger than this many bytes (0 = no limit)")
    parser.add_argument("--dry-run", action="store_true", help="Do not download media; only render text and metadata")
    parser.add_argument("--lang", type=str, default=os.environ.get("EXPORT_LANG", "ru"), choices=["en", "ru"], help="Interface language (default: ru; use 'en' to switch)")
    parser.add_argument("--lang-file", type=str, default=os.environ.get("EXPORT_LANG_FILE", ""), help="Path to JSON with translation overrides { key: template }")
    parser.add_argument("--keep-last", type=int, default=int(os.environ.get("EXPORT_KEEP_LAST", "0")), help="After export, keep only the last N export runs (0 = keep all)")
    return parser.parse_args()


def ensure_output_dirs(base_dir: Path) -> Tuple[Path, Path]:
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    run_dir = base_dir / f"saved_messages_{timestamp}"
    media_dir = run_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, media_dir


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def safe_filename(name: str) -> str:
    name = "".join(c for c in name if c.isalnum() or c in (" ", ".", "-", "_"))
    name = name.strip().replace(" ", "_")
    return name or "file"


def escape_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(text).replace("\n", "<br>")


_URL_RE = re.compile(r"(?P<url>(?:https?://|www\\.)[^\s<]+)")


def linkify_text(escaped_text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        url = match.group("url")
        href = url
        if url.startswith("www."):
            href = "http://" + url
        return (
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{url}</a>'
        )

    # Only operate on already-escaped plain text with <br> tags; avoid touching inside tags
    return _URL_RE.sub(_repl, escaped_text)


CUSTOM_TRANSLATIONS: dict[str, str] = {}


def t(lang: str, key: str) -> str:
    if key in CUSTOM_TRANSLATIONS:
        return CUSTOM_TRANSLATIONS[key]
    ru = {
        "title_base": "Сохранённые сообщения Telegram",
        "title_of": "Сохранённые сообщения Telegram пользователя {id}",
        "exported_at": "Экспорт выполнен {when} | Всего сообщений: {count}",
        "forwarded_from": "Переслано от {source}",
        "media_skipped": "медиа пропущено (>{limit} байт)",
        "media_not_downloaded": "медиа не скачано (dry-run)",
        "transcription": "Транскрипция",
        "progress": "Экспорт сообщений: {done} / {total}",
        "progress_no_total": "Экспорт сообщений: {done}",
    }
    en = {
        "title_base": "Telegram Saved Messages",
        "title_of": "Telegram Saved Messages of {id}",
        "exported_at": "Exported at {when} | Total messages: {count}",
        "forwarded_from": "Forwarded from {source}",
        "media_skipped": "media skipped (>{limit} bytes)",
        "media_not_downloaded": "media not downloaded (dry-run)",
        "transcription": "Transcription",
        "progress": "Exporting messages: {done} / {total}",
        "progress_no_total": "Exporting messages: {done}",
    }
    table = ru if lang == "ru" else en
    return table.get(key, key)


def format_ui_datetime(lang: str, dt_utc: datetime) -> str:
    local = dt_utc.astimezone()
    if lang == "ru":
        return local.strftime("%d.%m.%Y %H:%M:%S %Z")
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")

async def render_forwarded_from(client: TelegramClient, message: Message) -> Optional[str]:
    fwd = getattr(message, "fwd_from", None)
    if not fwd:
        return None
    # Prefer explicit from_name if present
    name = getattr(fwd, "from_name", None)
    if name:
        return html.escape(name)
    # Try from_id or saved_from_peer
    peer = getattr(fwd, "from_id", None) or getattr(fwd, "saved_from_peer", None)
    if not peer:
        return None
    try:
        ent = await client.get_entity(peer)
        title = getattr(ent, "title", None)
        first_name = getattr(ent, "first_name", None)
        last_name = getattr(ent, "last_name", None)
        username = getattr(ent, "username", None)
        display = title or (" ".join([n for n in [first_name, last_name] if n]) or None)
        if not display:
            return None
        display = html.escape(display)
        if username:
            return f'<a href="https://t.me/{html.escape(username)}" target="_blank" rel="noopener noreferrer">{display}</a>'
        return display
    except Exception:
        return None


def detect_extension(message: Message) -> str:
    if isinstance(message.media, MessageMediaPhoto):
        return ".jpg"
    if isinstance(message.media, MessageMediaDocument):
        # Try to infer extension from document attributes/name
        doc = message.document
        if doc and doc.attributes:
            for a in doc.attributes:
                fname = getattr(a, "file_name", None)
                if fname and "." in fname:
                    return os.path.splitext(fname)[1]
        # Fallback
        mime = getattr(doc, "mime_type", None) if doc else None
        if mime:
            if "/" in mime:
                return "." + mime.split("/")[-1]
    return ""


def decide_media_tag(rel_path: str, mimetype: Optional[str]) -> str:
    if mimetype:
        if mimetype.startswith("image/"):
            return f'<img class="media-img" src="{html.escape(rel_path)}" loading="lazy" alt="image" />'
        if mimetype.startswith("video/"):
            return f'<video class="media-vid" src="{html.escape(rel_path)}" controls preload="metadata"></video>'
        if mimetype.startswith("audio/"):
            return f'<audio class="media-aud" src="{html.escape(rel_path)}" controls preload="metadata"></audio>'
    # default: downloadable link
    file_name = os.path.basename(rel_path)
    return f'<a class="file-link" href="{html.escape(rel_path)}" download>{html.escape(file_name)}</a>'


async def ensure_login(client: TelegramClient) -> None:
    await client.connect()
    if await client.is_user_authorized():
        return
    phone = os.environ.get("TELEGRAM_PHONE")
    if not phone:
        print("First-run authentication required. Set TELEGRAM_PHONE env var or run interactively.")
        phone = input("Phone number (international format, e.g. +123456789): ").strip()
    await client.send_code_request(phone)
    code = os.environ.get("TELEGRAM_CODE") or input("Login code: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        pwd = os.environ.get("TELEGRAM_2FA_PASSWORD") or input("Two-step verification password: ")
        await client.sign_in(password=pwd)


async def transcribe_media_if_needed(local_path: Path, mimetype: Optional[str], enabled: bool, model_name: str, language: str) -> Optional[str]:
    return None


async def transcribe_with_telegram(client: TelegramClient, message: Message) -> Optional[str]:
    try:
        me = await client.get_me()
        is_premium = bool(getattr(me, "premium", False))
        if not is_premium:
            return None
    except Exception:
        return None

    # Only voice notes and round video messages are supported
    is_voice = False
    is_round_video = False
    if getattr(message, "document", None) and getattr(message.document, "attributes", None):
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeAudio) and getattr(attr, "voice", False):
                is_voice = True
            if isinstance(attr, DocumentAttributeVideo) and getattr(attr, "round_message", False):
                is_round_video = True

    if not (is_voice or is_round_video):
        return None

    try:
        result = await client(tl_functions.messages.TranscribeAudioRequest(peer="me", msg_id=message.id))
        # result may be messages.TranscribedAudio with .text
        text = getattr(result, "text", None)
        if text:
            return str(text).strip()
    except Exception as e:  # noqa: BLE001
        # Silently ignore if Telegram refuses or not supported
        print(f"Telegram transcription failed for message {message.id}: {e}")
        return None
    return None
    global _whisper_import_error_printed
    try:
        import whisper  # type: ignore
    except Exception as e:  # noqa: BLE001
        if not _whisper_import_error_printed:
            print(f"Transcription disabled: whisper not available ({e}). Install 'openai-whisper' and ffmpeg.")
            _whisper_import_error_printed = True
        return None

    def _run() -> str:
        model = whisper.load_model(model_name)
        # whisper expects str path
        result = model.transcribe(str(local_path), language=language or None)
        text = result.get("text") or ""
        return text.strip()

    try:
        text: str = await asyncio.to_thread(_run)
        return text or None
    except Exception as e:  # noqa: BLE001
        print(f"Transcription failed for {local_path}: {e}")
        return None


async def export_saved_messages(args: argparse.Namespace) -> Path:
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir, media_dir = ensure_output_dirs(output_dir)

    def _parse_ddmmyyyy(value: str) -> datetime:
        # Parse as UTC midnight
        dt = datetime.strptime(value, "%d-%m-%Y").replace(tzinfo=timezone.utc)
        return dt

    since_dt: Optional[datetime] = _parse_ddmmyyyy(args.since) if args.since else None
    until_dt: Optional[datetime] = _parse_ddmmyyyy(args.until) if args.until else None
    # Make until inclusive by advancing to the next day's midnight and using < comparison
    if until_dt:
        until_dt_exclusive: Optional[datetime] = until_dt + timedelta(days=1)
    elif since_dt:
        # If only --since provided, cap until to "now" (UTC), inclusive
        until_dt_exclusive = datetime.now(timezone.utc) + timedelta(seconds=1)
    else:
        until_dt_exclusive = None

    # Initialize client: session can be file path or StringSession
    session_arg: str | StringSession
    if os.path.exists(args.session):
        session_arg = args.session
    else:
        session_arg = StringSession(args.session) if args.session and len(args.session) > 100 else args.session

    # Load custom translations if provided
    global CUSTOM_TRANSLATIONS
    CUSTOM_TRANSLATIONS = {}
    if args.lang_file:
        try:
            CUSTOM_TRANSLATIONS = json.loads(Path(args.lang_file).read_text(encoding="utf-8"))
            if not isinstance(CUSTOM_TRANSLATIONS, dict):
                CUSTOM_TRANSLATIONS = {}
        except Exception as e:  # noqa: BLE001
            print(f"Failed to load language file {args.lang_file}: {e}")

    client = TelegramClient(session_arg, args.api_id, args.api_hash)
    await ensure_login(client)

    # Resolve current user's phone and username for title/header
    try:
        me = await client.get_me()
        me_phone = getattr(me, "phone", None)
        me_username = getattr(me, "username", None)
        phone_display = ("+" + me_phone) if me_phone and not me_phone.startswith("+") else (me_phone or None)
        if args.lang == "ru":
            if phone_display and me_username:
                export_title = f"Сохранённые сообщения Telegram пользователя {phone_display} ({me_username})"
            elif phone_display:
                export_title = f"Сохранённые сообщения Telegram пользователя {phone_display}"
            elif me_username:
                export_title = f"Сохранённые сообщения Telegram пользователя {me_username}"
            else:
                export_title = t(args.lang, "title_base")
        else:
            if phone_display and me_username:
                export_title = f"Telegram Saved Messages of {phone_display} ({me_username})"
            elif phone_display:
                export_title = f"Telegram Saved Messages of {phone_display}"
            elif me_username:
                export_title = f"Telegram Saved Messages of {me_username}"
            else:
                export_title = t(args.lang, "title_base")
    except Exception:
        export_title = t(args.lang, "title_base")

    total = 0
    messages_html: list[str] = []
    progress_total: Optional[int] = None
    # Pre-count messages that match filters so the progress total reflects the export size
    try:
        cnt = 0
        itc = client.iter_messages("me", reverse=args.reverse)
        async for m in itc:
            if not isinstance(m, Message):
                continue
            dt = m.date
            dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            if since_dt and dt_utc < since_dt:
                continue
            if until_dt_exclusive and dt_utc >= until_dt_exclusive:
                continue
            cnt += 1
        progress_total = cnt
    except Exception:
        progress_total = None

    # Iterate messages from Saved Messages
    it = client.iter_messages("me", reverse=args.reverse)
    async for message in it:
        if not isinstance(message, Message):
            continue
        # Normalize message date to UTC and ensure tz-aware
        msg_dt = message.date
        msg_dt_utc = msg_dt.astimezone(timezone.utc) if msg_dt.tzinfo else msg_dt.replace(tzinfo=timezone.utc)
        if since_dt and msg_dt_utc < since_dt:
            continue
        if until_dt_exclusive and msg_dt_utc >= until_dt_exclusive:
            continue

        total += 1
        if progress_total:
            print(f"\rExporting messages: {total} / {progress_total}", end="", flush=True)
        else:
            print(f"\rExporting messages: {total}", end="", flush=True)
        msg_id = message.id
        date_str = format_ui_datetime(args.lang, msg_dt_utc)
        text_html = linkify_text(escape_text(message.message))

        media_html = ""
        if message.media:
            # Handle Telegram web page previews first
            if isinstance(message.media, MessageMediaWebPage):
                preview_html = ""
                try:
                    webpage = message.media.webpage
                    site = html.escape(getattr(webpage, "site_name", "") or "")
                    title = html.escape(getattr(webpage, "title", "") or "")
                    desc = html.escape(getattr(webpage, "description", "") or "")
                    url = html.escape(getattr(webpage, "url", "") or "")
                    thumb_rel = None
                    if getattr(webpage, "photo", None) and not args.dry_run:
                        # Save thumbnail image next to media
                        base_name = safe_filename(f"preview_{msg_id}_{message.date.strftime('%Y%m%d_%H%M%S')}") + ".jpg"
                        target_path = media_dir / base_name
                        try:
                            downloaded = await client.download_media(webpage.photo, file=target_path)
                            if downloaded:
                                thumb_rel = os.path.relpath(str(downloaded), str(run_dir))
                        except Exception as e:  # noqa: BLE001
                            print(f"Failed to download link preview thumbnail for message {msg_id}: {e}")
                    img_html = f'<div class="thumb"><img src="{html.escape(thumb_rel)}" alt="preview"/></div>' if thumb_rel else '<div class="thumb"></div>'
                    meta_html = (
                        '<div class="meta">'
                        + (f'<div class="site">{site}</div>' if site else "")
                        + (f'<div class="title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title or url}</a></div>')
                        + (f'<div class="desc">{desc}</div>' if desc else "")
                        + '</div>'
                    )
                    preview_html = f'<div class="link-preview">{img_html}{meta_html}</div>'
                except Exception as e:  # noqa: BLE001
                    preview_html = f'<div class="media"><span class="badge">link preview unavailable</span></div>'
                    print(f"Link preview rendering failed for message {msg_id}: {e}")
                media_html = preview_html
            else:
                # Attempt to skip large files if requested
                if args.max_bytes and getattr(message, "document", None) and getattr(message.document, "size", 0) > args.max_bytes:
                    media_html = f'<span class="badge">media skipped (>{args.max_bytes} bytes)</span>'
                else:
                    rel_media_path = None
                    mimetype = None
                    local_media_path: Optional[Path] = None
                    if not args.dry_run:
                        # File name: msgid_date.ext
                        ext = detect_extension(message)
                        base_name = safe_filename(f"msg_{msg_id}_{message.date.strftime('%Y%m%d_%H%M%S')}") + ext
                        target_path = media_dir / base_name
                        try:
                            downloaded = await message.download_media(file=target_path)
                            if downloaded:
                                rel_media_path = os.path.relpath(str(downloaded), str(run_dir))
                                local_media_path = Path(downloaded)
                        except Exception as e:  # noqa: BLE001
                            rel_media_path = None
                            print(f"Failed to download media for message {msg_id}: {e}")
                    # Try to detect mimetype after download
                    if getattr(message, "document", None):
                        mimetype = getattr(message.document, "mime_type", None)
                    if getattr(message, "photo", None):
                        mimetype = "image/jpeg"

                    if rel_media_path:
                        tag_html = decide_media_tag(rel_media_path, mimetype)
                        transcript_html = ""
                        # Auto-use Telegram transcription for Premium accounts when embedding audio/video
                        transcript_text: Optional[str] = None
                        transcript_text = await transcribe_with_telegram(client, message)
                        if transcript_text:
                            safe_transcript = html.escape(transcript_text)
                            label = "Текст" if args.lang == "ru" else "Transcription"
                            transcript_html = (
                                f'<details class="media"><summary class="badge">{label}</summary>'
                                f"<pre>{safe_transcript}</pre>"
                                "</details>"
                            )
                        media_html = f'<div class="media">{tag_html}{transcript_html}</div>'
                    else:
                        if args.dry_run:
                            media_html = '<div class="media"><span class="badge">media not downloaded (dry-run)</span></div>'

        fwd_html = ""
        fwd_from_label = await render_forwarded_from(client, message)
        if fwd_from_label:
            fwd_html = f'<div class="msg-fwd">{t(args.lang, "forwarded_from").format(source=fwd_from_label)}</div>'

        block = (
            f'<div class="message" id="msg-{msg_id}">'
            f'<div class="msg-head"><span class="msg-id">#{msg_id}</span>'
            f'<span class="msg-date">{html.escape(date_str)}</span></div>'
            f'{fwd_html}'
            f'<div class="msg-text">{text_html or ""}</div>'
            f'{media_html}'
            f"</div>"
        )
        messages_html.append(block)

    # Reconcile last line to N / N if total was different
    if progress_total and total != progress_total:
        print(f"\rExporting messages: {total} / {total}", end="", flush=True)
    print()

    html_doc = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(export_title)}</title>\n<style>{CSS_STYLE}</style>\n"
        "</head>\n<body>\n"
        "<div class=\"header\">\n"
        f"  <h1 class=\"title\">{html.escape(export_title)}</h1>\n"
        f"  <div class=\"meta\">{html.escape(t(args.lang, 'exported_at').format(when=format_ui_datetime(args.lang, datetime.now(timezone.utc)), count=total))}</div>\n"
        "</div>\n"
        "<div class=\"container\">\n"
        + "\n".join(messages_html) +
        "\n</div>\n</body>\n</html>\n"
    )

    index_path = run_dir / "index.html"
    index_path.write_text(html_doc, encoding="utf-8")

    # Zip the run directory
    archive_base = str(run_dir)
    zip_path = shutil.make_archive(archive_base, "zip", root_dir=str(run_dir))
    print(f"Export complete. HTML: {index_path}\nArchive: {zip_path}")
    # Optionally prune old exports
    try:
        if args.keep_last and args.keep_last > 0:
            base_dir = Path(args.output).expanduser().resolve()
            # Collect all export run folders matching naming scheme
            runs = []
            for p in sorted(base_dir.glob("saved_messages_*")):
                if p.is_dir():
                    runs.append(p)
            # Sort by folder name (contains timestamp), lexicographic order works
            runs.sort(key=lambda p: p.name)
            # Determine which to delete (all but the last N)
            to_delete = runs[:-args.keep_last] if len(runs) > args.keep_last else []
            for old_run in to_delete:
                try:
                    # Remove zip archive if exists
                    zip_candidate = Path(str(old_run) + ".zip")
                    if zip_candidate.exists():
                        zip_candidate.unlink()
                    # Remove the directory tree
                    shutil.rmtree(old_run, ignore_errors=True)
                    print(f"Pruned old export: {old_run}")
                except Exception as e:  # noqa: BLE001
                    print(f"Failed to prune {old_run}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"Cleanup failed: {e}")
    await client.disconnect()
    return run_dir


def main() -> int:
    args = parse_args()
    if not args.api_id or not args.api_hash:
        print("Missing API credentials. Set --api-id/--api-hash or TELEGRAM_API_ID/TELEGRAM_API_HASH.")
        return 2
    try:
        asyncio.run(export_saved_messages(args))
        return 0
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


