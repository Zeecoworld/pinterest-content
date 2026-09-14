# Zeecomedia Pinterest Content Manager

A Django dashboard for planning, scheduling, and (eventually) auto-posting
Pinterest content for the Zeecomedia brand — built for near-daily tech/AI pins.

## Features

- **Dashboard** — pin counts, 7-day posting activity chart, category
  breakdown, upcoming scheduled pins, automation status
- **Content manager** — grid view with filters, create/edit form with image
  upload + live preview, detail page, delete confirmation
- **Calendar** — month view of scheduled/posted pins
- **Boards & Categories** — organize pins by Pinterest board and content theme
- **Automation settings** — on/off switch, Pinterest API token fields,
  posting frequency & time window, active weekdays, content rules
  (auto-hashtags, AI-flagged-only posting), failure email notifications
- **`run_auto_post` management command** — the hook point for real automation
  (cron / Celery beat / systemd timer); the Pinterest API call itself is left
  as one clearly-marked function (`publish_to_pinterest`) for you to fill in
  with your API credentials

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo_data   # creates admin/admin123 + sample content
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` and log in with `admin` / `admin123`
(change this password immediately — see below).

## Connecting Pinterest for real

1. Create an app at <https://developers.pinterest.com/> and generate an
   access token with the `boards:read`, `pins:read`, `pins:write` scopes.
2. Go to **Automation Settings** in the dashboard and paste the token + app
   ID, pick a default board, set your posting window/frequency/days.
3. Open `pins/management/commands/run_auto_post.py` and implement
   `publish_to_pinterest()` with the real API call (a commented example
   using `requests` is already in the docstring).
4. Schedule the command to run regularly, e.g. every 15 minutes:
   ```bash
   */15 * * * * cd /path/to/project && venv/bin/python manage.py run_auto_post
   ```
   Or wire it into Celery beat if you're already running Celery elsewhere.

The command respects everything set in Automation Settings: it only posts
on active weekdays, inside the configured time window, and (optionally)
only content flagged as AI-generated.

## Production notes

- Set `DEBUG = False`, a real `SECRET_KEY`, and proper `ALLOWED_HOSTS` in
  `config/settings.py` (or better, load them from environment variables).
- Swap SQLite for Postgres by changing `DATABASES` in `config/settings.py`.
- Serve `MEDIA_ROOT` (pin images) via S3/Cloudinary/Supabase Storage or your
  reverse proxy — Django's built-in static serving in `urls.py` is dev-only.
- Change the default admin password immediately:
  `python manage.py changepassword admin`

## Project structure

```
config/          Django project settings & root URLs
pins/            The app: models, views, forms, admin, templates
  templates/pins/        Dashboard, content, calendar, boards, categories, settings
  templates/registration/  Login page
  management/commands/   run_auto_post.py, seed_demo_data.py
media/           Uploaded pin images (created at runtime)
```
