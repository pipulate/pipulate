{
  description = "Minimal Sovereign Jekyll Environment Flake (Zero-Minima, Dynamic Ruby ABI)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        useIncrementalBuild = true;

        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          requests
          tiktoken
          pyyaml
          rich
        ]);

        commonHook = ''
          useIncrementalBuild="${if useIncrementalBuild then "true" else "false"}"

          export GEM_HOME=$PWD/.gem
          export GEM_PATH=$GEM_HOME:$GEM_PATH
          export PATH=$GEM_HOME/bin:$PATH
          export BUNDLE_FORCE_RUBY_PLATFORM=1

          export LD_LIBRARY_PATH="${pkgs.ruby}/lib:${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
          export LD_LIBRARY_PATH="${pkgs.libffi}/lib:$LD_LIBRARY_PATH"
          export LD_LIBRARY_PATH="${pkgs.zlib}/lib:$LD_LIBRARY_PATH"
          export LD_LIBRARY_PATH="${pkgs.libxml2}/lib:$LD_LIBRARY_PATH"
          export LD_LIBRARY_PATH="${pkgs.libxslt}/lib:$LD_LIBRARY_PATH"

          export PKG_CONFIG_PATH="${pkgs.zlib.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"
          export PKG_CONFIG_PATH="${pkgs.libffi.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"
          export PKG_CONFIG_PATH="${pkgs.libxml2.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"
          export PKG_CONFIG_PATH="${pkgs.libxslt.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"
          export PKG_CONFIG_PATH="${pkgs.openssl.dev}/lib/pkgconfig:$PKG_CONFIG_PATH"
          export BUNDLE_BUILD__EVENTMACHINE="--with-cflags=-I${pkgs.openssl.dev}/include"

          if ! gem list -i bundler > /dev/null 2>&1; then
            echo "Installing bundler..."
            gem install bundler --no-document
          fi

          bundle config set --local path "$GEM_HOME"
          bundle config set --local build.nokogiri --use-system-libraries
          bundle config set --local build.ffi --enable-system-libffi
          bundle config set --local build.eventmachine --with-cflags="-I${pkgs.openssl.dev}/include"
          bundle config set --local force_ruby_platform true

          alias vim=nvim
          export PS1="\[\033[1;32m\](nix)\[\033[0m\] \[\033[1;34m\]\W\[\033[0m\] $ "
          alias isnix="echo '✓ In Nix shell'"

          jes() {
            current_dir=$(pwd)
            site_root="$current_dir"
            while [[ "$site_root" != "/" && ! -f "$site_root/Gemfile" ]]; do
              site_root="$(dirname "$site_root")"
            done
            if [[ ! -f "$site_root/Gemfile" ]]; then
              echo "Error: Could not find Gemfile."
              return 1
            fi
            if [ -f "$site_root/.port" ]; then
              port=$(cat "$site_root/.port")
            else
              port=4000
            fi

            check_ruby_version() {
              export GEM_HOME="$site_root/.gem"
              export GEM_PATH="$GEM_HOME"
              export PATH="$GEM_HOME/bin:$PATH"
              export BUNDLE_GEMFILE="$site_root/Gemfile"
              export BUNDLE_PATH="$GEM_HOME"

              local ruby_abi
              ruby_abi=$(ruby -e 'print RbConfig::CONFIG["ruby_version"]' 2>/dev/null || echo "3.4.0")

              if [ ! -f "$site_root/.gem/ruby/$ruby_abi/bin/jekyll" ]; then
                rm -rf "$site_root/.gem"
                return 1
              fi

              if ! (cd "$site_root" && bundle exec jekyll --version >/dev/null 2>&1); then
                rm -rf "$site_root/.gem"
                return 1
              fi

              local broken_so
              broken_so=$(find "$site_root/.gem/ruby/$ruby_abi" -name "*.so" -exec ldd {} + 2>&1 | grep "not found" || true)
              if [ -n "$broken_so" ]; then
                rm -rf "$site_root/.gem"
                return 1
              fi

              if ! (cd "$site_root" && bundle check >/dev/null 2>&1); then
                rm -rf "$site_root/.gem"
                return 1
              fi
              return 0
            }

            if ! check_ruby_version; then
              echo "Rebuilding Ruby environment..."
              (cd "$site_root" && gem install bundler --no-document && BUNDLE_FORCE_RUBY_PLATFORM=1 RUBYOPT="-W0" bundle install)
            fi

            pkill -f "jekyll serve.*$site_root" || true
            sleep 1
            local jekyll_build_flags="--verbose --incremental"
            if [ "$useIncrementalBuild" = "false" ]; then
              jekyll_build_flags="--verbose"
            fi
            cd "$site_root"
            RUBYOPT="-W0" bundle exec jekyll serve $jekyll_build_flags --port $port --host 0.0.0.0
            cd "$current_dir"
          }

          jes-stop() {
            pkill -f "jekyll serve" || true
          }
        '';

        buildInputs = [
          pkgs.ruby
          pkgs.neovim
          pkgs.git
          pythonEnv
          pkgs.stdenv.cc.cc.lib
          pkgs.pkg-config
          pkgs.openssl
          pkgs.zlib
          pkgs.libffi
          pkgs.libxml2
          pkgs.libxslt
        ];
      in
      {
        devShells = {
          default = pkgs.mkShell {
            inherit buildInputs;
            shellHook = ''
              ${commonHook}
              if [ -z "$PIPULATE_PROD" ]; then
                jes
              fi
            '';
          };
          quiet = pkgs.mkShell {
            inherit buildInputs;
            shellHook = ''
              ${commonHook}
              echo "Jekyll environment ready (quiet mode). Run 'jes' to start."
            '';
          };
        };
      });
}
