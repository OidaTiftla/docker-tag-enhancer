{ pkgs ? import <nixpkgs> { } }:
with pkgs;
mkShell {
  buildInputs = [
    nixpkgs-fmt
    python314
    skopeo
    jq
  ];

  shellHook = ''
    echo "docker-tag-enhancer environment loaded"
    export PYTHONPATH="$PWD/src:$PYTHONPATH"
  '';
}
