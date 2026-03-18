{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          # Backend — Python 3.12 + uv
          python312
          uv

          # Native libs needed by Python packages
          ghostscript # camelot-py[ghostscript]
          file # python-magic (libmagic)
          postgresql # psycopg (pg_config)

          # Frontend — Node + pnpm
          nodejs
          pnpm

          # Infrastructure
          docker-compose

          # LSPs and tools
          # Python
          ty
          ruff
          python3Packages.docformatter # Python docstrings
          # vue3
          vue-language-server
          vtsls # TypeScript/JavaScript
          vscode-langservers-extracted # CSS, HTML, JSON, ESLint LSPs
          jq # JSON
          nodePackages.prettier # JS/TS/JSON/YAML/MD fallback
          prettierd # Prettier daemon
          oxlint # JS/TS

          # Other
          docker-language-server # Dockerfiles
          marksman # Markdown
          taplo # TOML
          markdownlint-cli # Markdown
        ];

        env = {
          # Help python-magic find libmagic
          MAGIC = "${pkgs.file}/lib/libmagic.so";
        };

        shellHook = ''
          # Use uv-managed venv if it exists
          if [ -d .venv ]; then
            export VIRTUAL_ENV="$PWD/.venv"
            export PATH="$VIRTUAL_ENV/bin:$PATH"
          fi
        '';
      };
    };
}
