# CLAUDE.md

## Project Overview

Valentina Discord Bot (`vbot`) is a Discord bot for playing White Wolf TTRPGs. It connects to a central Valentina API for data persistence and uses a local SQLite database as a cache. The bot is built with py-cord (Discord.py fork) using the cogs pattern for command organization.

## Commands

```bash
uv run ruff format .                      # Format python code
uv run ruff check .                       # Check python code without fixing
uv run mypy src/                          # Run mypy type checking for python code
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

- **Config** (`src/vbot/config/`): Application settings via pydantic-settings (`base.py`) and Tortoise ORM database configuration (`db.py`)
- **Bot** (`src/vbot/bot/`): Main bot class extending `commands.Bot` with custom context classes (`ValentinaContext`, `ValentinaAutocompleteContext`) that provide API user resolution
- **Cogs** (`src/vbot/cogs/`): Thin command definitions organized by domain (admin, campaign, character, gameplay, user, developer, events, storyteller). Each cog has a `cog.py` with slash commands. Shared modules at the cogs level include `autocompletion.py` (common autocomplete helpers) and `validators.py`. Individual cogs may have their own `autocomplete.py` (e.g., admin)
- **Views** (`src/vbot/views/`): Reusable Discord UI primitives — buttons, embeds, modals, select menus
- **Workflows** (`src/vbot/workflows/`): Multi-step Discord interaction flows — character creation wizards (autogeneration, manual entry, quick gen), trait reallocation, character sheet display, campaign viewer, dice rolls, asset review, confirmation actions
- **Handlers** (`src/vbot/handlers/`): API/DB sync layer — bridges between `vclient` API services and the local SQLite cache (assets, book, campaign, character, user, database handlers)
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

## Testing

- Tests use Tortoise ORM with in-memory SQLite via `tortoise_test_context` fixture (`tests/conftest.py`)
- **vclient.testing factories**: Use `CampaignFactory.build()`, `UserFactory.build()`, `CharacterFactory.build()`, `CampaignBookFactory.build()`, etc. from `vclient.testing` to create test DTOs. Pass keyword overrides to customize fields (e.g., `UserFactory.build(id="u-001", role="PLAYER")`)
- **FakeVClient**: Handler tests use the `fake_vclient` fixture which provides a `FakeVClient` that intercepts all vclient HTTP calls. Register responses with `fake_vclient.add_route(method, Endpoints.X, json=..., status_code=...)`. Paginated list responses use shape `{"items": [...], "total": N, "limit": 100, "offset": 0}`. Single objects use `obj.model_dump(mode="json")`
- Discord objects (Member, Guild, Context) are mocked via factory fixtures in `conftest.py`

## Types and Constants

Domain types shared with the Valentina API (e.g., `CharacterClass`, `CharacterStatus`, `CharacterType`, `GameVersion`, `UserRole`, `DiceSize`) are `Literal` type aliases imported from `vclient.constants`. They are plain strings (or ints for `DiceSize`) — not Enums. Use string comparisons (`character.type == "PLAYER"`) and `get_args()` when you need to iterate over valid values.

Bot-only types in `src/vbot/constants.py`: `EmbedColor`, `ChannelPermission`, `CampaignChannelName`, `LogLevel` are Enums. `EmojiDict` is a plain class (not an Enum) used as a namespace for emoji constants.

## Gotchas

- **Environment files**: Settings loads from `.env.secret` (project root, gitignored) using the `VALBOT_` prefix with `__` as the nested delimiter (e.g., `VALBOT_DISCORD__TOKEN`, `VALBOT_API__BASE_URL`)
- **vclient imports at call site**: Some vclient imports (e.g., `users_service`, `options_service`) are done inside functions rather than at module level to avoid circular imports and startup failures
