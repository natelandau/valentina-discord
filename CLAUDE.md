# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Valentina Discord Bot (`vbot`) is a Discord bot for playing White Wolf TTRPGs. It connects to a central Valentina API for data persistence and uses a local SQLite database as a cache. The bot is built with py-cord (Discord.py fork) using the cogs pattern for command organization.

## Commands

```bash
uv run ruff format .                      # Format code
uv run ruff check .                       # Check code without fixing
uv run mypy src/                          # Run mypy type checking
uv run duty lint                          # Run all linting (ruff, mypy, typos, format)
uv run duty test                          # Run tests with coverage
uv run duty clean                         # Clean build artifacts
uv run vbot                               # Run the bot

# Single test or specific tests
uv run pytest tests/path/to/test_file.py -x
uv run pytest tests/ -k "test_name_pattern" -x
```

## Architecture

### Core Components

- **Bot** (`src/vbot/bot/`): Main bot class extending `commands.Bot` with custom context classes (`ValentinaContext`, `ValentinaAutocompleteContext`) that provide API user resolution
- **Cogs** (`src/vbot/cogs/`): Thin command definitions organized by domain (admin, campaign, character, gameplay, user, developer, events, storyteller). Each cog has a `cog.py` with slash commands and optional `autocompletion.py`
- **Views** (`src/vbot/views/`): Reusable Discord UI primitives — buttons, embeds, modals, select menus
- **Workflows** (`src/vbot/workflows/`): Multi-step Discord interaction flows — character creation wizards (autogeneration, manual entry, quick gen), trait reallocation, character sheet display, campaign viewer, dice rolls, confirmation actions
- **Handlers** (`src/vbot/handlers/`): API/DB sync layer — bridges between `vclient` API services and the local SQLite cache (book, campaign, character, user, database handlers)
- **Lib** (`src/vbot/lib/`): Core library modules - `ChannelManager` (campaign channel lifecycle), `character_sheet_builder`, `exceptions`, `validation`, `logging`
- **Utils** (`src/vbot/utils/`): Utility functions - Discord helpers (`set_user_role`, `assert_permissions`, `fetch_channel_object`), string formatting (`num_to_circles`, `truncate_string`), time helpers
- **DB Models** (`src/vbot/db/models/`): Tortoise ORM models for local SQLite cache (Server, DBUser, DBCampaign, DBCharacter, DBCampaignBook)

### Data Flow

1. Discord commands are handled by cogs
2. Cogs invoke workflows for multi-step interactions (wizards, character sheets, dice rolls)
3. Cogs and workflows call `vclient` services directly for API operations
4. When data needs local caching, handlers sync between API and SQLite database
5. `ValentinaContext.get_api_user_id()` resolves Discord users to API users

### Key Patterns

- **Cog Registration**: Cogs auto-discovered from `src/vbot/cogs/**/cog.py` and must include a `setup(bot)` function
- **Slash Command Groups**: Use `discord.SlashCommandGroup` with subgroups for nested commands (e.g., `/admin user link`)
- **Confirmation Actions**: Use `confirm_action()` from workflows for destructive operations
- **Channel Management**: `ChannelManager` creates/manages campaign-specific Discord channels

## Configuration

Settings loaded via pydantic-settings from environment variables with prefix `VALBOT_`:

- `VALBOT_DISCORD__TOKEN` - Discord bot token
- `VALBOT_DISCORD__GUILDS` - Comma-separated guild IDs
- `VALBOT_DISCORD__OWNER_IDS` - Comma-separated owner Discord IDs
- `VALBOT_DISCORD__OWNER_CHANNELS` - Comma-separated owner channel IDs
- `VALBOT_API_SERVICE__URL` - Valentina API URL
- `VALBOT_API_SERVICE__API_KEY` - API key
- `VALBOT_API_SERVICE__COMPANY_ID` - Company ID
- `VALBOT_DATABASE_PATH` - SQLite database path (default: `data/database.db`)
- `VALBOT_LOG_FILE_PATH` - Log file path
- `VALBOT_LOG_LEVEL` - Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)

## External Dependencies

- **valentina-python-client** (`vclient`): Python client for Valentina API. Services accessed via `users_service()`, `characters_service()`, `campaigns_service()`, etc.
- **py-cord**: Discord API wrapper (not discord.py)
- **Tortoise ORM**: Async ORM for SQLite database

## Testing

- Tests use Tortoise ORM with in-memory SQLite via `tortoise_test_context` fixture (`tests/conftest.py`)
- vclient services are mocked with `pytest-mock` - fixtures: `mock_campaigns_service`, `mock_users_service`, `mock_books_service`, `mock_characters_service`
- Discord objects (Member, Guild, Context) are mocked via factory fixtures in `conftest.py`
- Test factories in `tests/factories.py` for creating test data

## Types and Constants

Domain types shared with the Valentina API (e.g., `CharacterClass`, `CharacterStatus`, `CharacterType`, `GameVersion`, `UserRole`, `DiceSize`) are `Literal` type aliases imported from `vclient.constants`. They are plain strings (or ints for `DiceSize`) — not Enums. Use string comparisons (`character.type == "PLAYER"`) and `get_args()` when you need to iterate over valid values.

Bot-only types in `src/vbot/constants.py` remain as local Enums: `EmojiDict`, `EmbedColor`, `ChannelPermission`, `CampaignChannelName`, `LogLevel`.

## Gotchas

- **Environment files**: Settings loads from `.env` and `.env.secret` (both in project root, gitignored)
- **vclient imports at call site**: Some vclient imports (e.g., `users_service`, `options_service`) are done inside functions rather than at module level to avoid circular imports and startup failures

## Documentation and Resources

- **Valentina Python Client Documentation**: https://docs.valentina-noir.com/python-api-client/
- **Valentina Python Client Codebase**: ../valentina-python-client/
