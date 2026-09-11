# Homebuster

A community fork/rework of [TheMarveled/movie-cataloguer](https://github.com/TheMarveled/movie-cataloguer), focused on self-hosted personal and shared physical movie collections.

The original project is MIT licensed. This fork keeps the physical-media catalogue idea and core movie metadata while adding accounts, private/shared Libraries, permissions, Shelves, and Loans.

## What is new

- Username/password login with no email requirement.
- Optional public registration controlled by `ALLOW_REGISTRATION=true|false`.
- Site admins can reset passwords, disable accounts, grant/revoke admin status, and safely delete users.
- Site-admin status **does not grant access to users' Movie Libraries**.
- Every account can own multiple private Libraries and join shared Libraries.
- Shared Library roles: **Owner**, **Editor**, and **Viewer**.
- Library ownership can be transferred, including a completely private Library.
- Safe user deletion: every owned Library must be transferred or deliberately deleted first.
- Shelves for physical organization, including an Unassigned state.
- Loans with borrower name, optional phone, loan date, notes, return action, and retained history.
- Existing-style Collections for franchises/groups such as `Evil Dead`.
- Search and filters for status, format, shelf, collection, and loan availability.
- CSV import/export per Library.
- TMDb identification for title/year/poster when `TMDB_API_KEY` is configured.
- TMDb-first Add Movie search with a manual-entry fallback.
- SQLite WAL mode and automatic backups before destructive Library/user operations.
- Legacy Movie Cataloguer database migration.
- Docker/Compose deployment using a persistent `./data` directory.

## Quick Docker start

```bash
cp .env.example .env
mkdir -p data
```

Edit `.env` before the first start. At minimum, give the initial admin a real password:

```env
ALLOW_REGISTRATION=false
PASSWORD_MIN_LENGTH=8
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=use-a-long-unique-password-here
```

Then run:

```bash
docker compose up -d --build
```

Open:

```text
http://YOUR-SERVER-IP:8080
```

After the admin account has been created successfully, remove `INITIAL_ADMIN_PASSWORD` from `.env` (or leave it blank) and restart the container. Existing accounts are not overwritten by the bootstrap variables.

### Create or promote an admin from the CLI

You can also create a site admin without using bootstrap environment variables:

```bash
docker compose exec homebuster flask --app app create-admin admin
```

The command prompts for the password without echoing it. If that username already exists, it resets the password and grants site-admin status.

The Docker container is named `Homebuster`, so its logs can be viewed with `docker logs Homebuster`. Homebuster also identifies itself by name in its startup log.

## Registration

Registration defaults to disabled:

```env
ALLOW_REGISTRATION=false
PASSWORD_MIN_LENGTH=8
```

`PASSWORD_MIN_LENGTH` controls the minimum password length for registration, admin password resets, first-boot admins, and the `create-admin` CLI command.

Turn it on when you want new users to create accounts:

```env
ALLOW_REGISTRATION=true
```

No email address is collected. Each registration automatically creates a private `My Movies` Library.

## Permissions

Permissions belong to a Library, not to the site account globally.

| Role | View | Add/edit/delete movies | Shelves/Collections/Loans | Share/manage members | Transfer/delete Library |
|---|---:|---:|---:|---:|---:|
| Viewer | Yes | No | No | No | No |
| Editor | Yes | Yes | Yes | No | No |
| Owner | Yes | Yes | Yes | Yes | Yes |

A site admin can manage user accounts but cannot open a Library unless its owner explicitly shares that Library with the admin's normal user account.

## Migrating an existing `movies.db`

The original Movie Cataloguer database can be migrated in place.

1. Stop the old application.
2. Make your own backup of `movies.db` first.
3. Copy the old database to this fork as:

```text
./data/movies.db
```

4. Set `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` for the first boot. The migrated movies need an account to own their new Library.
5. Run `docker compose up -d --build`.

On startup, the app detects the old `movies` table because it has no `library_id`. It creates an automatic `pre-migration-*.db` backup under:

```text
./data/backups/
```

Then it migrates the movie rows into the initial account's `My Movies` Library. Existing movie integer IDs and existing Collection IDs/relationships are preserved.

The migrated fields include the original project's:

- barcode
- title
- year
- format
- poster path
- TMDb ID
- owned/wanted status
- version/edition
- country
- language
- region
- disc count
- notes
- Collections and movie/Collection links

## Backups

Before clearing a Library, deleting a Library, or deleting a user, the app creates a SQLite backup in:

```text
./data/backups/
```

These are not a replacement for your normal off-site backups. Back up the entire `./data` directory with the rest of your server data.

Keep the live SQLite database on a local filesystem. Backing it up to SMB/NFS is fine, but avoid running the live `movies.db` directly from a network share.

## Reverse proxy / Internet hosting

For Internet exposure, put the container behind HTTPS with your existing reverse proxy. When the browser always reaches the site through HTTPS, set:

```env
SESSION_COOKIE_SECURE=true
```

The app uses HTTP-only, SameSite=Lax session cookies and CSRF protection for state-changing forms.

Do not expose Flask's development server. The Docker image runs Gunicorn.

## TMDb

Set an API key in `.env`:

```env
TMDB_API_KEY=your_key_here
```

From a movie's detail page, Editors and Owners can choose **Identify with TMDb** and select the correct search result. This updates the movie's title, year, poster, and TMDb ID.

## CSV

CSV export is scoped to the Library currently open. Imports support the original metadata plus two useful columns:

- `shelf` — shelf name; missing shelves are created automatically.
- `collections` — semicolon-separated Collection names.

Export columns:

```text
barcode,title,year,format,poster_path,tmdb_id,status,version,country,language,region,disc_count,notes,shelf,collections
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_PATH="$PWD/data/movies.db"
export ALLOW_REGISTRATION=true
flask --app app create-admin admin
flask --app app run --debug
```

Run tests with:

```bash
pytest -q
```

## Project layout

```text
app.py
movie_catalogue/
  __init__.py
  admin.py
  auth.py
  catalog.py
  config.py
  db.py
  libraries.py
  permissions.py
  static/styles.css
  templates/
tests/
Dockerfile
docker-compose.yml
.env.example
```

## Notes about this first fork

The original project had a large single-page JavaScript UI including bulk-edit operations. This rework intentionally prioritizes the new multi-user security model and the core catalogue workflows in smaller Flask modules. Movie CRUD, metadata, search/filtering, CSV, Collections, and TMDb matching are present, but the original bulk-edit toolbar is not yet reproduced.

## Attribution and license

Based on **Movie Cataloguer** by TheMarveled:

https://github.com/TheMarveled/movie-cataloguer

Released under the MIT License. See `LICENSE`.


## Android companion app (v0.3.6)

The existing Homebuster web interface remains the primary browser interface. The `android/` directory contains a companion Android client that connects to the same Flask server and SQLite database through `/api/v1`.

Third-party service credentials stay on the server. The Android APK stores only the Homebuster server URL and its revocable login token. Configure TMDb and optional barcode lookup keys in the server `.env`; never put them in the Android project.

Build the Android debug APK from `android/` with Android Studio or `./gradlew assembleDebug`.
