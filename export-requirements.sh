#!/usr/bin/env bash

set -e

echo "[Running] poetry install"
poetry install

echo "[Running] poetry export"
poetry export --format=requirements.txt --output=requirements.txt --without-hashes

echo "[Success] requirements.txt exported"
