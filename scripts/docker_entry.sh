#! /usr/bin/env bash

if not command -v uv &> /dev/null; then
    echo "uv is not installed"
    exit 1
fi

# Run the server
uv run --no-dev vbot
