## Release 1.8

Release date: September 9, 2026

## New Features

- Download a whole series, season or playlist by sending the link with the `/series`
  command (aliases: `/season`, `/playlist`), e.g.
  ```
  /series https://arte.tv/de/videos/RC-027708/happy-valley
  ```
  The worker resolves the link into the single videos behind it (flattening nested
  collections, e.g. one collection per season) and queues each of them as its own
  download task. The bot replies with the number of queued videos and then reports every
  episode separately, as with any other download.
- Same feature via the API by adding `"playlist": true` to the `POST /v1/tasks` payload.
- Failed downloads are now retried automatically. The worker re-queues them after
  `RESEND_DELAY_MS` (default 60s), up to `CONSUMER_NUMBER_OF_RETRY` times (default 2),
  and only reports the failure to Telegram after the last attempt. Both variables
  already existed in the configuration but were never used.
- Re-sending a series link downloads only what is missing: entries that already have a
  completed task, or one that is still queued, are skipped. Failed entries are
  re-queued, so recovering from a partly failed series is just sending the link again.
- Host configuration for the German KiKA (`kika.de`). KiKA offers every resolution both
  as HLS and as a plain MP4, and now the plain file is preferred: one request instead of
  several hundred fragments at the same resolution, which makes downloading a whole
  series much less likely to fail.
- More resilient downloads: `yt-dlp` had no retry backoff configured at all, so all
  retries fired within a couple of seconds. Fragment and HTTP retries now back off
  exponentially (2s → 15s), which fixes dropped connections against throttling CDNs
  such as arte.tv when downloading a whole series.

## Fixes

- `MAX_SIMULTANEOUS_DOWNLOADS` is now actually enforced. It was applied as the RabbitMQ
  prefetch count, but the worker acknowledges a message before starting its download, so
  the broker kept delivering and every delivery is handled in its own task. The real
  limit was the size of the default asyncio executor, `min(32, cpu_count + 4)`, which is
  8 downloads at once on a 4 core machine regardless of the configured value. Barely
  noticeable when pasting a couple of links, but a series queues dozens at once.

## Important

- New `MAX_PLAYLIST_ITEMS` variable in `envs/worker.env` (default `100`) caps how many
  videos are queued from a single playlist link. Add it to your `envs/worker.env` or
  leave it out to use the default.
- A new `info.q` queue and `info.dx` exchange are declared automatically on startup, no
  manual RabbitMQ action is needed.
- New `STALE_TASK_HOURS` variable in `envs/worker.env` (default `6`), after which an
  unfinished download counts as orphaned and is queued again instead of being skipped
  forever. Leave it out to use the default.
- New `CONSUMER_NUMBER_OF_RETRY` and `RESEND_DELAY_MS` variables in `envs/common.env`.
  Both fall back to their previous defaults when absent, so adding them is optional.
  `CONSUMER_NUMBER_OF_RETRY` now accepts `0` to turn retrying off.
- If you use a custom `app_worker/ytdl_opts/user.py`, the new `PLAYLIST_YTDL_OPTS`
  option set is taken from `default.py` unless you copy it over to your `user.py`.

## Misc

- GitHub Actions workflow publishing the `bot`, `worker` and `api` images to the GitHub
  Container Registry, plus `docker-compose.ghcr.yml` to run them without a local build.
- `shell.nix` for NixOS users, providing `ruff`, `uv`, `yt-dlp` and `ffmpeg` for local
  linting and debugging.

---

## Release 1.7

Release date: May 30, 2024

## New Features

- Choose `yt-dlp` release channel between `NIGHTLY`, `STABLE` or `MASTER`. Default is `NIGHTLY`.

## Important

- Update your `app_bot/config.yaml` with new `release_channel: "NIGHTLY"` line in `ytdlp` section
- `app_worker/requirements.txt` includes `NIGHTLY` `yt-dlp` package to install.

## Misc

N/A

---

## Release 1.6

Release date: April 25, 2024

## New Features

 - Ability to set custom video name in `POST` API request:
   ```json
    {
        "url": "<VIDEO_URL>",
        "download_media_type": "VIDEO",
        "save_to_storage": true,
        "custom_filename": "your cool custom name and extension.mp4",
        "automatic_extension": false
    }
   ```
 - Saving into storage with the same name won't overwrite the file but append timestamp to the filename.

## Important

N/A

## Misc

N/A

---

## Release 1.5

Release date: March 20, 2024

## New Features

N/A

## Important

N/A

## Misc

- Migrated from Pyrogram to Pyrofork
- Migrated from Python 3.11 to 3.12

---

## Release 1.4.5

Release date: November 23, 2023

## New Features

N/A

## Important

N/A

## Misc

- Improved error handling

---

## Release 1.4.4

Release date: November 11, 2023

## New Features

- New boolean config variable per user `is_admin`. Currently, admin users will receive update message when `yt-dlp` needs update.
  ```yaml
  allowed_users:
    - id: 11111111111
      is_admin: !!bool True
      ***
  ```

## Important

- Every user in the config must include this new config variable whether it's `True` or `False`

## Misc

N/A

---

## Release 1.4.3

Release date: September 20, 2023

## New Features

- Encode Instagram VP9 videos to H264 (not played in Telegram on iOS)
- New environment variable in `envs/.env_worker`: `INSTAGRAM_ENCODE_TO_H264=True`

## Important

N/A

## Misc

- Maintenance and refactor

---

## Release 1.4.2

Release date: July 06, 2023

## New Features

- Use cookies for website auth for download by putting them into the `app_worker/cookies/cookies.txt` file in Netscape
  format.

## Important

- If you are using the customized yt-dlp options in the `app_worker/ytdl_opts/user.py` you must reconfigure them from
  the updated `app_worker/ytdl_opts/default.py`.

## Misc

N/A

---

## Release 1.4.1

Release date: March 29, 2023

## New Features

N/A

## Important

N/A

## Misc

 - Maintenance release: added `uvloop`.

---

## Release 1.4

Release date: March 29, 2023

## New Features

- Enable or disable URL match against the regex. If you use the bot in the group with
  other people and don't want the bot to try to download any text message sent to the
  group, you can enable `use_url_regex_match: !!bool True` in the `app_bot/config.yml`
  so the bot will skip messages not matching URL regexes. You can add your own if
  needed.

## Important

1. Two new variables introduced in the `app_bot/config-example.yml`
    1. ```yaml
       url_validation_regexes:
         - "^http(s)?:\\/\\/.+$"
       ```
    2. ```yaml
       use_url_regex_match: !!bool True
       ```

## Misc

N/A

---

## Release 1.3

Release date: March 28, 2023

## New Features

- Now any user which is in the configured group with the bot can send the link

## Important

N/A

## Misc

N/A

---

## Release 1.2.1

Release date: March 22, 2023

## New Features

N/A (Maintenance release)

## Important

1. Disabled SQL logs by default: `SQLALCHEMY_ECHO=False` in `envs/.env_common`

## Misc

1. Improved upload log messages - now include file size and whether upload of the file is cached

---

## Release 1.2

Release date: March 13, 2023

## New Features

- Show message when media was saved to storage.

## Important

N/A

## Misc

N/A

---

## Release 1.1

Release date: March 11, 2023

## New Features

- Show uploaded file size in human-readable format.

## Important

* Added new config variable `include_size: !!bool True` for displaying uploaded file
  size.

## Misc

N/A

---

## Release 1.0

Release date: February 25, 2023

## New Features

1. Now bot can download audio (mp3), video (default), or both. Just configure the
   preferred mode for the particular user/group.

## Important

1. Changed content yt-dlp options in `app_worker/ytdl_opts/default.py`
2. Added two new user config options in `app_bot/config-example.yml`:
    1. `download_media_type`: What to download - audio (mp3), video or both. Values can
       be `AUDIO`, `VIDEO`, `AUDIO_VIDEO`.
    2. `save_to_storage`: Moved from `envs/.env_worker`
3. Creating task on API now requires previously mentioned two fields in payload to be
   sent.

## Misc

N/A


---

## Release 0.9

Release date: February 16, 2023

## New Features

N/A

## Important

1. Changed format of `YTDL_OPTS` in `app_worker/ytdl_opts/default.py` from `dict`
   to `list` for proper parsing on `yt_dlp` side:
   ```python
   # Old format
   YTDL_OPTS = {
       'outtmpl': '%(title).200B.%(ext)s',
       'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
       'noplaylist': True,
       'playlist_items': '1:1',
       'writethumbnail': True,
       'concurrent_fragment_downloads': 5,
   }
   
   # New format
   YTDL_OPTS = [
       '--output',
       '%(title).200B.%(ext)s',
       '--format',
       'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
       '--no-playlist',
       '--playlist-items',
       '1:1',
       '--write-thumbnail',
       '--convert-thumbnails',
       'jpg',
       '--concurrent-fragments',
       '5',
       '--verbose',
   ]
   ```
   This means only `yt-dlp` CLI options can be added (`yt-dlp --help` to list all of
   them).

## Misc

N/A

---

## Release 0.8

Release date: February 15, 2023

## New Features

1. yt-dlp will now try to download video thumbnail if it exists. This is done by
   setting `'writethumbnail': True` in `app_worker/ytdl_opts/default.py`. If thumbnail
   wasn't downloaded, `ffmpeg` task will create it as previously.

## Important

N/A

## Misc

N/A

---

## Release 0.7

Release date: February 5, 2023

## New Features

N/A

## Important

1. Configuration variable `TMP_DOWNLOAD_PATH` renamed to `TMP_DOWNLOAD_ROOT_PATH`
   in `envs/.env_common`.
2. Added 2 new configuration variables `TMP_DOWNLOAD_DIR` and `TMP_DOWNLOADED_DIR`
   to `envs/.env_common`.
3. Fixed bug [#52](https://github.com/tropicoo/yt-dlp-bot/issues/52).

## Misc

N/A


---

## Release 0.6

Release date: January 31, 2023

## New Features

N/A

## Important

N/A

## Misc

1. API bugfixes
2. Renamed microservices directories, e.g. `api` -> `app_api`

---

## Release 0.5

Release date: January 21, 2023

## New Features

1. Updated handling failed video download logic. In case of failed post-processing by
   yt-dlp, the (broken) video file could still remain in the temporary directory.
   This update handles this potential issue.

## Important

N/A

## Misc

N/A

---

## Release 0.4

Release date: November 13, 2022

## New Features

N/A

## Important

1. Changed default yt-dlp options in `worker/ytdl_opts/default.py`.
   Replaced `'max_downloads': 1` with `'playlist_items': '1:1'`
   to properly handle the result.
2. It's important to know that the worker backend does not handle downloading more than
   one video from the playlist even if you change yt-dlp options. Only the first video
   will be downloaded and processed.

## Misc

N/A

---

## Release 0.3.1

Release date: November 11, 2022

## New Features

* This is maintenance release. No New Features. Bumped `fastapi` and `SQLAlchemy`
  versions, updated README.

## Important

N/A

## Misc

N/A

---

## Release 0.3

Release date: November 7, 2022

## New Features

1. New or changed config variables in `bot/config-template.yml`:
    1. `send_startup_message` - send startup messages (per user in config) or not
    2. Fixed typo in `upload_vide_file` -> `upload_video_file`
    3. `ytdlp_version_check_interval` variable replaced with a new `ytdlp` config
       section:
        1. `version_check_enabled` - check for the new `yt-dlp` version or not
        2. `version_check_interval` - check interval in seconds when enabled,
           default `86400` (24 hours)
        3. `notify_users_on_new_version` - send a notification to Telegram chats about
           the new `yt-dlp` version or not (only log records will contain the message
           about the new version) for every user in the config

## Important

1. Default config template `bot/config-template.yml` was changed, reconfiguration needed

## Misc

1. Updated README
