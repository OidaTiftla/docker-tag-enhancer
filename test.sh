#!/usr/bin/env bash

set -e

cd src && python -m unittest discover -p 'test_*.py' -v

echo ""
echo -e "\033[0;32m✅ All tests passed!\033[0m"
