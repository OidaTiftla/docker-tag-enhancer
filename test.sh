#!/usr/bin/env bash

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment if it exists and is not already activated
if [ -n "$VIRTUAL_ENV" ] && [ "$VIRTUAL_ENV" != "$SCRIPT_DIR/venv" ]; then
    echo "Warning: A different virtual environment is already activated."
    echo "Please deactivate it first by running 'deactivate' and then rerun this script."
    exit 1
fi
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Activating virtual environment..."
        source "$SCRIPT_DIR/venv/bin/activate"
    fi
else
    echo "No virtual environment found at $SCRIPT_DIR/venv. Please create one and install dependencies."
    echo "You can create a virtual environment with the following commands:"
    echo "  \$ python -m venv venv"
    echo "  \$ source venv/bin/activate"
    echo "  \$ pip install -r src/requirements.txt"
    echo "Then rerun this script."
    echo "If you want to deactivate the virtual environment later, use:"
    echo "  \$ deactivate"
    exit 1
fi

echo ""
echo "Installed packages:"
pip install -r "$SCRIPT_DIR/src/requirements.txt"

echo ""
echo "Running lint checks..."
cd "$SCRIPT_DIR" && python -m flake8 src/run.py src/test_run.py src/test_integration.py --max-line-length=120 --extend-ignore=E501,W503,E302,E125,F841,E713

echo ""
echo "Running tests..."
cd "$SCRIPT_DIR/src" && python -m unittest discover -p 'test_*.py' -v

echo ""
echo -e "\033[0;32m✅ All tests and linting passed!\033[0m"
