# Shared package kernel for Jekyll development environments.
# Site flakes own Gemfiles, Python tools, shell hooks, and servers.
{ pkgs }:

[
  pkgs.ruby
  pkgs.neovim
  pkgs.git
  pkgs.stdenv.cc.cc.lib
  pkgs.pkg-config
  pkgs.openssl
  pkgs.zlib
  pkgs.libffi
  pkgs.libxml2
  pkgs.libxslt
]
