#!/usr/bin/env bash

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Running lint checks..."
cd "$SCRIPT_DIR" && python -m flake8 src/run.py src/test_run.py src/test_integration.py --max-line-length=120 --extend-ignore=E501,W503,E302,E125,F841,E713

echo ""
echo "Running tests..."
cd "$SCRIPT_DIR/src" && python -m unittest discover -p 'test_*.py' -v

echo ""
echo -e "\033[0;32m✅ All tests and linting passed!\033[0m"
