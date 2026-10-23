# ANIFLIX ANIME INDEX BOT

A Telegram anime catalogue bot built with Python 3.11, aiogram 3, SQLite, and pytest. It supports one central catalogue for private chats and eligible public/private groups, bulk imports, aliases, a shared landscape poster, a configurable global post-text template, backups, and Railway deployment.

## Features

- Exact, case-insensitive, partial, and alias search without commands in private chats and eligible groups.
- SQLite-only persistence (`DATABASE_PATH`, default `data/aniflix.db`) with foreign keys, WAL mode, indexes, unique title/URL constraints, and non-destructive startup.
- Authorized `/admin` inline panel with statistics, single/bulk add, edit, delete, links, aliases, global post text, shared poster, welcome/start image, backups, restore, and settings.
- Bulk format: `🍥 Naruto - https://example.com/naruto - green (post text)`. Color is optional and defaults to blue. Valid lines save independently and the response includes line-level diagnostics.
- One shared landscape image for all results. It is separate from the global post text and from optional individual poster metadata.
- Versioned `ANIFLIX_Anime_Backup.json` export and validated, confirmation-based additive restore.

## Global Post Text

The separate **📝 Post Text** menu controls one SQLite-backed template for all results. Its exact default is:

```text
🍥 {anime_title}

🎭 Genre: Action | Adventure | Comedy
🎙️ Audio: Tamil
📺 Quality: 480p | 720p | 1080p

👇 Click the below button to download episodes!

⚠️ If Any Issues, Message here:
https://t.me/+4YfcdPoSdK9jYmVl

🔗 Click the below button to join!
```

Use **Edit Post Text** to replace the complete template and **Preview** to render a sample title. `{anime_title}` is replaced immediately at send time. If an anime has non-empty individual `post_text`, that individual text takes precedence; otherwise the global template is used. The download button always uses that anime record's own URL.

The separate **📝 Manage Posts** menu controls only the shared landscape image. If the image is unavailable or the caption exceeds Telegram's 1024-character photo-caption limit, the bot falls back to text messages without changing the download link.

## Local setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Required variables:

- `BOT_TOKEN`: token from BotFather.
- `OWNER_ID`: numeric Telegram user ID of the owner.
- `ADMIN_IDS`: optional comma-separated numeric IDs.
- `DATABASE_PATH`: optional SQLite path, default `data/aniflix.db`.
- `MEDIA_DIR`: optional media directory, default `data/media`.

No MongoDB variables, packages, or services are used.

## Telegram and group configuration

1. Create the bot with BotFather and put the token in Railway or `.env`; never commit it.
2. Set `OWNER_ID` and optional `ADMIN_IDS`. Group administrator status does not grant access to `/admin`.
3. Add the bot to each target group and grant permission to read and reply to messages.
4. For direct, non-command group searches, use BotFather `/setprivacy` → select the bot → `Disable`. The application cannot change BotFather settings. With privacy mode enabled, Telegram may not deliver ordinary group messages.
5. Test a private chat and multiple group IDs after deployment. No group registration or hardcoded group ID is used.

## Railway deployment and persistence

Deploy with the included `Dockerfile` or `railway.toml`. Set `BOT_TOKEN`, `OWNER_ID`, and optional `ADMIN_IDS` in the Railway service. Attach a Railway Volume mounted at `/app/data`. Set `DATABASE_PATH=/app/data/aniflix.db` and `MEDIA_DIR=/app/data/media` so SQLite and Telegram media references are under the persistent mount. Persistence depends on the volume being correctly attached and mounted; it has not been live-verified here. View startup/polling logs in Railway. Run one polling worker for SQLite concurrency safety.

## Admin usage

Use `/admin` as the owner or configured admin. The **➕ Add Anime** and **📦 Bulk Add Anime** buttons set a one-message workflow. `/edit <id> <new title>`, `/setlink <id> <https URL>`, `/delete <id>`, `/addalias <id> <alias>`, and `/removealias <id> <alias>` provide safe catalogue maintenance. `/setwelcome text` saves the welcome message. Reply to a photo with `/setposter` or use **Manage Posts → Set Landscape Poster**. `/setstartimage` configures the start image. Upload `ANIFLIX_Anime_Backup.json` to preview and confirm an additive restore. `/cancel` cancels pending workflows.

## Tests

```bash
pytest -q
python -m compileall -q .
```

The suite uses temporary SQLite databases and covers parser errors, 55 valid entries saved/retrieved, mixed batches, repeated imports, duplicates, aliases, CRUD, correct links, global post-text substitution and restart persistence, backup validation, and configuration. Live Telegram API behavior, BotFather privacy settings, and Railway volume persistence require manual verification with real credentials and are not claimed as tested.
