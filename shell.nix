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
    export PYTHONPATH="$PWD/src:$PYTHONPATH"
  '';
}
