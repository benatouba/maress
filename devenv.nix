{ pkgs, lib, ... }:
let
  typstPreviewPackages = pkgs.runCommandLocal "typst-packages-preview" { } ''
    mkdir -p "$out/preview"
    ln -s "${pkgs.typstPackages.touying}/lib/typst-packages/touying" "$out/preview/touying"
  '';
in
{
  dotenv = {
    enable = true;
    filename = ".env.local";
  };

  # --- Languages ---
  languages.python = {
    enable = true;
    package = pkgs.python312.withPackages (ps: [
      ps.python-magic
    ]);
    uv = {
      enable = true;
      sync.enable = true; # auto-sync from pyproject.toml
    };
    directory = "./backend";
    venv = {
      enable = true;
      quiet = true;
    };
    manylinux = {
      enable = true;
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
    libGL
    glib
    gcc
    tesseract
    libc

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
    typst
  ];

  # --- Services ---
  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    extensions = ext: [ ext.postgis ];
    initialDatabases = [ { name = "maress"; } ];
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
    UV_LINK_MODE = "copy";
    PGDATABASE = "maress";
    TYPST_PACKAGE_PATH = "${typstPreviewPackages}";

    LD_LIBRARY_PATH = lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.libGL
      pkgs.glib
      pkgs.tesseract
    ];
  };

  # --- Processes (start with `devenv up`) ---
  processes = {
    migrate = {
      exec = ''
        while ! pg_isready -q; do sleep 0.2; done
        db_exists="$(psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='maress'")"
        if [ "$db_exists" != "1" ]; then
          createdb maress
        fi
        cd backend && uv run alembic upgrade head
      '';
    };
    backend = {
      exec = "cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload";
      process-compose = {
        depends_on.migrate.condition = "process_completed_successfully";
      };
    };
    worker = {
      exec = "cd backend && env -u CELERY_BROKER_URL -u CELERY_RESULT_BACKEND uv run celery -A app.celery_app worker --loglevel=info --concurrency=\${CELERY_WORKER_CONCURRENCY:-2}";
      watch = {
        paths = [
          ./backend/app/tasks
          ./backend/app/celery_app.py
        ];
        extensions = [ "py" ];
      };
      process-compose = {
        depends_on.migrate.condition = "process_completed_successfully";
      };
    };
    frontend.exec = "cd frontend && pnpm dev";
  };

  scripts.db-drop-maress = {
    description = "Start postgres, drop maress DB, stop postgres";
    exec = ''
      started_here=0

      if ! pg_isready -q; then
        start-postgres >/tmp/maress-db-drop-postgres.log 2>&1 &
        postgres_pid=$!
        started_here=1

        while ! pg_isready -q; do sleep 0.2; done
      fi

      dropdb --if-exists maress

      if [ "$started_here" = "1" ]; then
        pg_ctl -D "$PGDATA" -m fast stop
        wait "$postgres_pid" 2>/dev/null || true
      fi
    '';
  };

  enterShell = ''
    echo "maress dev environment"
    echo "  devenv up    — start postgres + redis + backend + worker + frontend"
    echo "  backend:  cd backend && uv run uvicorn app.main:app --reload"
    echo "  worker:   cd backend && env -u CELERY_BROKER_URL -u CELERY_RESULT_BACKEND uv run celery -A app.celery_app worker --concurrency=\$CELERY_WORKER_CONCURRENCY"
    echo "  frontend: cd frontend && pnpm dev"
    echo "  typst:    typst compile project-presentation/nfdi4earth-dresden-2026.typ"
  '';
}
