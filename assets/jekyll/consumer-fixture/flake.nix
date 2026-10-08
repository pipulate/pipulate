{
  description = "Independent consumer fixture for Pipulate's Jekyll package kernel";

  inputs.pipulate = {
    url = "github:pipulate/pipulate";
    flake = false;
  };

  outputs = { self, pipulate }:
    let
      pkgs = {
        ruby = "ruby";
        neovim = "neovim";
        git = "git";
        stdenv.cc.cc.lib = "cc-lib";
        pkg-config = "pkg-config";
        openssl = "openssl";
        zlib = "zlib";
        libffi = "libffi";
        libxml2 = "libxml2";
        libxslt = "libxslt";
      };

      actual = import (pipulate + "/assets/jekyll/common-packages.nix") {
        inherit pkgs;
      };

      expected = [
        "ruby"
        "neovim"
        "git"
        "cc-lib"
        "pkg-config"
        "openssl"
        "zlib"
        "libffi"
        "libxml2"
        "libxslt"
      ];
    in
    {
      lib.jekyllKernelSmoke = assert actual == expected; actual;
    };
}
