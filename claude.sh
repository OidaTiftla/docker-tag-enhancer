#!/usr/bin/env bash

# escape each arg so spaces/quotes are preserved when building the single --run string
escaped_args=()
for a in "$@"; do
    escaped_args+=("$(printf '%q' "$a")")
done

# build command string (uncomment the next line to pass CONFIG too)
# cmd="claude --config $(printf '%q' "$CONFIG")"
cmd="MY_PATH=\"\$PATH\" claude"
if (( ${#escaped_args[@]} )); then
    joined="${escaped_args[*]}"
    cmd+=" $joined"
fi

NIXPKGS_ALLOW_UNFREE=1 nix-shell -p claude-code python314 skopeo jq --run "$cmd"
