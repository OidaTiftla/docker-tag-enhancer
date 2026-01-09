#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure direnv is installed and set up
if ! command -v direnv >/dev/null 2>&1; then
    echo "direnv not found, installing..."
    sudo apt update
    sudo apt install -y direnv
fi

# Set up direnv
if [ -f ~/.bashrc ] && ! grep -q 'direnv hook bash' ~/.bashrc; then
    echo 'Enabling direnv for bash...'
    echo '# Enable direnv' >> ~/.bashrc
    echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
fi
if [ -f ~/.zshrc ] && ! grep -q 'direnv hook zsh' ~/.zshrc; then
    echo 'Enabling direnv for zsh...'
    echo '# Enable direnv' >> ~/.zshrc
    echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
fi

# Create .envrc to use Nix flakes
if [ ! -f ".envrc" ]; then
    echo 'Creating .envrc to use Nix flakes...'
    echo 'use flake . --impure' >> .envrc
fi
if [ ! -f ~/.config/nix/nix.conf ] || ! grep -q 'experimental-features = nix-command flakes' ~/.config/nix/nix.conf; then
    echo 'Enabling Nix experimental features...'
    mkdir -p ~/.config/nix
    echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
fi

# Allow direnv
echo "Allowing direnv for the project..."
direnv allow
