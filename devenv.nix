{ pkgs, ... }:
{
  # --- Languages ---
  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv = {
      enable = true;
      sync.enable = true; # auto-sync from pyproject.toml
    };
    directory = "./backend";
    venv = {
      enable = true;
      quiet = true;
    };
  };

  languages.javascript = {
    enable = true;
    pnpm = {
      enable = true;
      install.enable = true; # auto-sync from package.json
    };
    directory = "./frontend";
  };

  # --- Native dependencies ---
  packages = with pkgs; [
    # Native libs needed by Python packages
    ghostscript # camelot-py[ghostscript]
    file # python-magic (libmagic)

    # LSPs and dev tools — Python
    ty
    ruff
    python3Packages.docformatter

    # LSPs and dev tools — Vue/TS
    vue-language-server
    vtsls
    vscode-langservers-extracted
    jq
    oxlint
    eslint
  ];

  # --- Services ---
  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    extensions = ext: [ ext.postgis ];
    initialDatabases = [{ name = "maress"; }];
    listen_addresses = "127.0.0.1";
    port = 5432;
  };

  services.redis = {
    enable = true;
    port = 6379;
  };

  # --- Environment ---
  env = {
    MAGIC = "${pkgs.file}/share/misc/magic.mgc";
  };

  # --- Processes (optional: start with `devenv up`) ---
  processes = {
    backend.exec = "cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload";
    worker.exec = "cd backend && uv run celery -A app.celery_app worker --loglevel=info";
    frontend.exec = "cd frontend && pnpm dev";
  };
}
