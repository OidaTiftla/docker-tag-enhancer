#!/usr/bin/env bash

# escape each arg so spaces/quotes are preserved when building the single --run string
escaped_args=()
for a in "$@"; do
    escaped_args+=("$(printf '%q' "$a")")
done

# build command string (uncomment the next line to pass CONFIG too)
# cmd="codex --config $(printf '%q' "$CONFIG")"
cmd="MY_PATH=\"\$PATH\" codex"
if (( ${#escaped_args[@]} )); then
    joined="${escaped_args[*]}"
    cmd+=" $joined"
fi

nix-shell -p codex --run "$cmd"
