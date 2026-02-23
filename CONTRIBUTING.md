# Contributing

Thank you for your interest in contributing to Valentina Noir! This document provides guidelines and instructions to make the contribution process smooth and effective.

## Development Setup

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. To start developing:

1. Install uv using the [recommended method](https://docs.astral.sh/uv/installation/) for your operating system
2. Clone this repository: `git clone https://github.com/natelandau/valentina-discord`
3. Navigate to the repository: `cd valentina-discord`
4. Install dependencies with uv: `uv sync`
5. Activate your virtual environment: `source .venv/bin/activate`
6. Install [prek](https://prek.j178.dev/) git hooks: `prek install`
7. [Install Docker](https://www.docker.com/get-started/) to run the development environment

### Running Tasks

We use [Duty](https://pawamoy.github.io/duty/) as our task runner. Common tasks:

- `duty --list` - List all available tasks
- `duty lint` - Run all linters
- `duty format` - Format the code
- `duty test` - Run all tests
- `duty clean` - Clean the project of all temporary files
- `duty update` - Update the project dependencies
- `duty run` - Run the bot

### Set environment variables

Copy the `.env.example` file to `.env.secrets` and add your own values to configure Valentina.

### Start the development environment

You can start the development environment with Docker by running:

```bash
# Start the development environment
docker compose up

# Trigger a rebuild of the Valentina container
docker compose up --build
```

Alternatively, you can run the bot outside of docker for faster development:

```bash
uv run vbot
```

> [!WARNING]\
> Running `duty dev-setup` or `duty clean` will delete all of the data in the development database. Use with caution.

### Running tests

To run tests, run `duty test`. This will run all tests in the `tests` directory.

```bash
duty test
```

### Convenience Discord Commands

Once the development environment is running, the following slash commands are available in your test Discord Server:

- `/developer guild reset_discord_channels` - Reset the Discord channels for the current guild. **IMPORTANT: This is a destructive action and will delete all channels in the guild.**
- `/developer api_status` - Get the status of the Valentina API.
- `/admin user link-self` - Link your Discord account to a Valentina user.
- `/admin user link <discord_user> <valentina_user>` - Link a Discord user to a Valentina user.
- `/admin valentina resync` - Resync all data from the Valentina API and update all channels in the Discord server.

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Ensure code passes linting with `duty lint`
4. Ensure tests pass with `duty test`
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Push your branch and create a pull request

We use [Semantic Versioning](https://semver.org/) for version management.

## Troubleshooting

If connecting to Discord with the bot fails due to a certificate error, run `scripts/install_certifi.py` to install the latest certificate bundle.
