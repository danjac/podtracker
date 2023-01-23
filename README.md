This is the source code for a [simple, easy to use podcatcher web application](https://radiofeed.app). You are free to use this source to host the app yourself. The application is intended to be run in production in Heroku or a Heroku-like PAAS such as Dokku or Railway; however it should be quite easy to adapt it to run in other environments such as AWS EC2.

![desktop](/screenshots/desktop.png?raw=True)

## Running Radiofeed on your local machine

Radiofeed requires the following dependencies:

* Python 3.10+
* Node 16+
* pip-tools

### Additional requirements

For ease of local development a `docker-compose.yml` is provided which includes:

* PostgreSQL
* Redis
* Mailhog (for local email testing and development)

You can use these images if you want, or use a local install of PostgreSQL or Redis.

Current tested versions are PostgresSQL 14+ and Redis 6.2+.

## Development

You should first create a virtualenv before installing the application:

```bash
python -m venv .venv && source .venv/bin/activate
```

A `Makefile` has been provided to help with setting up your local development environment:

* `make build`: install and download front and backend dependencies
* `make compose`: start Docker services
* `make db`: run migrations and load sample fixtures

The following commands are useful while working on the project:

* `python manage.py runserver`: run the Django development server
* `python -m pytest`: run unit tests
* `npm run build:js`: compile JavaScript assets
* `npm run watch:js`: compile JavaScript assets on the fly
* `npm run build:css`: compile CSS assets (including Tailwind)
* `npm run watch:css`: compile CSS assets (including Tailwind) on the fly

If you are running several of these services simultaneously you should use a multiplexer such as Tmux.

## Deployment

The following environment variables should be set in your production installation (changing `radiofeed.app` for your domain).

```
DJANGO_SETTINGS_MODULE=radiofeed.settings.production
ALLOWED_HOSTS=radiofeed.app
DATABASE_URL=<database-url>
REDIS_URL=<redis-url>
ADMIN_URL=<admin-url>
ADMINS=me@radiofeed.app
EMAIL_HOST=mg.radiofeed.app
MAILGUN_API_KEY=<mailgun_api_key>
SECRET_KEY=<secret>
SENTRY_URL=<sentry-url>
```

Some settings such as `DATABASE_URL` may be set automatically by certain PAAS providers such as Heroku. Consult your provider documentation as required.

`EMAIL_HOST` should be set to your Mailgun sender domain along with `MAILGUN_API_KEY` if you are using Mailgun.

You should ensure the `SECRET_KEY` is sufficiently random: run the `generate_secret_key` custom Django command to create a suitable random string.

In production it's also a good idea to set `ADMIN_URL` to something other than the default _admin/_. Make sure it ends in a forward slash, e.g. _some-random-path/_.

A Dockerfile is provided for standard container deployments e.g. on Dokku.

Once you have access to the Django Admin, you should configure the default Site instance with the correct production name and domain.

### Crons

In production you should set up the following cron jobs to run these Django commands (with suggested schedules and arguments):

Parse podcast RSS feeds:

```bash
*/6 * * * * python manage.py parse_feeds
```

Generate similar recommendations for each podcast:

```bash
15 6 * * * python manage.py create_recommendations
```

Send podcast recommendations to users:

```bash
15 9 * * 1 python manage.py send_recommendations_emails
```

An `app.json` configuration with these cron schedules is included for Dokku deployment.
