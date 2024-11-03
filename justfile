site_domain := "localhost:8000"
site_name := "RadioFeed"

admin_username := "admin"
admin_email := "admin@localhost"

@_default:
    @just --list

# Install all dependencies
@install:
   @just envfile
   @just pyinstall
   @just precommmitinstall
   @just nltkdownload

# Update all dependencies
@update:
   @just pyupdate
   @just pyinstall
   @just precommitupdate

# Run all checks and tests
@check:
   @just typecheck
   @just templatecheck
   @just test
   @just precommitall

# Start Docker services, run migrations, and start the Django development server
@start:
   @just up
   @just migrate
   @just serve

# Deploy application using Github Actions
@deploy:
    gh workflow run deploy_production.yml

# Install all Python dependencies
@pyinstall:
   uv sync --frozen --all-extras --no-install-project

# Update all Python dependencies
@pyupdate:
   uv lock --upgrade

# Run the Django management command
@dj *ARGS:
   uv run python ./manage.py {{ ARGS }}

# Create a superuser
@superuser username=admin_username email=admin_email:
   @just dj createsuperuser \
        --noinput \
        --username="{{ username }}" \
        --email="{{ email }}"

# Run the Django development server
@serve:
   @just dj tailwind runserver_plus

# Run database migrations
@migrate:
   @just dj migrate

# Open the Django shell
@shell:
   @just dj shell_plus

# Clear the cache
@clearcache:
   @just dj clear_cache

# Validate all templates
@templatecheck:
   @just dj validate_templates

# Set the default site name and domain
@defaultsite name=site_name domain=site_domain:
    @just dj set_default_site --domain="{{ domain }}" --name="{{ name }}"

# Run unit tests
@test *ARGS:
   uv run pytest {{ ARGS }}

# Type check the code
@typecheck *ARGS:
   uv run pyright {{ ARGS }}

# Start all Docker services
@up *ARGS:
   docker compose up -d {{ ARGS }}

# Stop all Docker services
@down *ARGS:
   docker compose down {{ ARGS }}

# Run pre-commit manually
@precommit *ARGS:
   uv run --with pre-commit-uv pre-commit {{ ARGS }}

# Install pre-commit hooks
@precommmitinstall:
   @just precommit install
   @just precommit install --hook-type commit-msg

# Update pre-commit hooks
@precommitupdate:
   @just precommit autoupdate

# Re-run pre-commit on all files
@precommitall:
   @just precommit run --all-files

# Download NLTK data
@nltkdownload:
   uv run xargs -I{} python -c "import nltk; nltk.download('{}')" < ./nltk.txt

# Build local database and add default data
@dbinit:
   @just migrate
   @just defaultsite
   @just superuser

# Delete local database volume
[confirm]
@dbremove:
    docker volume rm radiofeed-app_pg_data

# Create a new .env file from .env.example if it doesn't exist
@envfile:
   cp -R -u -p .env.example .env

# Remove all untracked files and directories
[confirm]
@clean:
   git clean -Xdf
