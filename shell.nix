# Development shell for yt-dlp-bot.
#
#   nix-shell            # enter the shell
#   ruff check .         # lint with the config from pyproject.toml
#   ruff format --diff . # check formatting
#
# The applications themselves run in Docker (see docker-compose.yml); this shell only
# provides the tooling needed to lint and to poke at yt-dlp locally.
{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  name = "yt-dlp-bot";

  packages = with pkgs; [
    python312
    uv
    ruff
    yt-dlp
    ffmpeg
    docker-compose
  ];

  shellHook = ''
    echo "yt-dlp-bot dev shell: $(ruff --version), $(yt-dlp --version)"
  '';
}
