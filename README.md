# ANIFLIX ANIME INDEX BOT

A production-oriented Telegram anime catalogue bot built with Python 3.11, aiogram 3, SQLite, and pytest. It supports private-chat and eligible group searches from one central catalogue, bulk imports, aliases, a shared landscape poster, backups, and Railway deployment.

## Features

- Case-insensitive exact, partial, and alias search in private chats and group chats.
- SQLite-only persistence (`DATABASE_PATH`, default `data/aniflix.db`) with foreign keys, WAL mode, unique title/URL constraints, and non-destructive startup.
- Authorized `/admin` inline panel with statistics, bulk add, backup, restore, shared poster guidance, welcome message, settings, and administration controls. Every displayed option has a callback handler; configuration-only options explain their safe operational path.
- Bulk format: `🍥 Naruto - https://example.com/naruto - green (post text)`. Valid lines save independently; duplicates and invalid lines are counted accurately.
- One shared landscape image for all results. It is separate from individual artwork management.
- Versioned `ANIFLIX_Anime_Backup.json` export and validated, additive restore.

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

1. In BotFather, create a bot and put the token in Railway or `.env`; do not commit it.
2. Set `OWNER_ID` and optional `ADMIN_IDS`.
3. Add the bot to each target group and grant administrator permissions sufficient to read and reply to messages. Telegram group behavior also depends on privacy mode.
4. For direct, non-command group searches, disable privacy mode in BotFather with `/setprivacy` → select the bot → `Disable`. This is not changed by the application and must be done manually. If privacy mode remains enabled, Telegram may not deliver ordinary messages to the bot.
5. Test with different group IDs and a private chat after deployment. The application does not hardcode group IDs or require group registration.

## Railway deployment and persistence

Deploy this repository as a Railway service using the included `Dockerfile` or `railway.toml`. Configure the environment variables in the Railway service. Attach a Railway Volume mounted at `/app/data`; the included config uses `/app/data` for the database and media directory. Set `DATABASE_PATH=/app/data/aniflix.db` and optionally `MEDIA_DIR=/app/data/media` explicitly if desired. Persistence across deployments depends on the volume being attached and mounted correctly; it is not guaranteed by the container alone. View startup and polling logs in Railway.

## Admin operations

Use `/admin` as the owner or an authorized ID. Send a multiline bulk list for immediate import. Use `/setwelcome text` to set the welcome message. Reply to a landscape photo with `/setposter`; the file ID is stored in SQLite and used for every search result. Upload `ANIFLIX_Anime_Backup.json` for validated additive restore. Backups never include tokens or user secrets.

Search history stores only user ID, chat ID, a truncated query, and timestamp for basic statistics. Do not put sensitive information in search messages; administrators should treat the database as private.

## Tests and limitations

Run:

```bash
pytest -q
python -m compileall -q .
```

Live Telegram API behavior, BotFather privacy settings, and Railway volume persistence require manual verification with real credentials and are not claimed as tested in this repository. The shared poster uses Telegram `file_id`, with a text fallback if Telegram cannot retrieve it. SQLite is designed for one polling worker, as configured here.
