# Valentina Discord Bot

A Discord bot for the [Valentina Noir](https://docs.valentina-noir.com/) ecosystem. It is built with [py-cord](https://docs.pycord.dev/) and provides all of the functionality of the [Valentina API](https://docs.valentina-noir.com/) in a Discord bot.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A running [Valentina API](https://docs.valentina-noir.com/python-api-client/) instance
- A [Discord bot token](https://discord.com/developers/applications)

## Quick Start

Clone the repository and install dependencies:

```bash
git clone https://github.com/natelandau/valentina-discord
cd valentina-discord
uv sync
```

Create your environment configuration:

```bash
cp .env.example .env.secret
```

Edit `.env.secret` with your credentials (see [Configuration](#configuration) below), then start the bot:

```bash
uv run vbot
```

## Configuration

Settings are loaded from environment variables with the `VALBOT_` prefix. The bot reads from a `.env.secret` file in the project root.

### Required

| Variable                         | Description                           |
| -------------------------------- | ------------------------------------- |
| `VALBOT_API__BASE_URL`           | Valentina API URL                     |
| `VALBOT_API__API_KEY`            | API authentication key                |
| `VALBOT_API__DEFAULT_COMPANY_ID` | Company ID for the API                |
| `VALBOT_DISCORD__TOKEN`          | Discord bot token                     |
| `VALBOT_DISCORD__GUILDS`         | Comma-separated Discord guild IDs     |
| `VALBOT_DISCORD__OWNER_IDS`      | Comma-separated bot owner Discord IDs |
| `VALBOT_DISCORD__OWNER_CHANNELS` | Comma-separated owner channel IDs     |

### Optional

| Variable                            | Default            | Description                                       |
| ----------------------------------- | ------------------ | ------------------------------------------------- |
| `VALBOT_API__TIMEOUT`               | `10.0`             | API request timeout in seconds                    |
| `VALBOT_API__MAX_RETRIES`           | `5`                | Max API retry attempts                            |
| `VALBOT_API__RETRY_DELAY`           | `1.0`              | Delay between retries in seconds                  |
| `VALBOT_API__AUTO_RETRY_RATE_LIMIT` | `true`             | Automatically retry on rate limit                 |
| `VALBOT_API__AUTO_IDEMPOTENCY_KEYS` | `true`             | Auto-generate idempotency keys                    |
| `VALBOT_API__ENABLE_LOGS`           | `false`            | Enable API request logging                        |
| `VALBOT_LOG_LEVEL`                  | `INFO`             | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `VALBOT_LOG_FILE_PATH`              | --                 | Path for log file output                          |
| `VALBOT_DATABASE_PATH`              | `data/database.db` | SQLite database path                              |

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

For development with auto-rebuild on file changes:

```bash
docker compose up --build --watch
```

The container mounts a `.dev/` directory for persistent logs and data. Environment variables are read from `.env.secret`.

## Bootstrap

After starting the bot for the first time, run these commands in your Discord server to set up:

1. `/admin user link-self` -- Link your Discord account to a Valentina user with admin permissions
2. `/admin user link <discord_user> <valentina_user>` -- Link any existing Discord users to Valentina users
3. `/admin valentina resync` -- Sync all channels and data from the Valentina API

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, running tests, and the commit process.

## License

[MIT](LICENSE)
