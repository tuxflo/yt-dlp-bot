## yt-dlp-bot - Video Download Telegram Bot 🇺🇦

Simple and reliable self-hosted Video Download Telegram Bot.

Version: 1.8.0. [Release details](RELEASES.md).

![frames](.assets/download_success.png)


## Support the development

- [Buy me a coffee](https://www.buymeacoffee.com/terletsky)
- PayPal [![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=MA6RKYAZH9DSA)
- Bitcoin wallet `14kMRS8SvfD2ydMSMEyAmefHV3Yynf9kAd`

## 😂 Features

* Download audio and free videos with Creative Commons (CC) License from [yt-dlp](https://github.com/yt-dlp/yt-dlp) sites to your storage.
* Download a whole series, season or playlist with the `/series` command.
* Upload downloaded media to Telegram.
* Interact with the bot in private or group chats.
* Trigger video downloads via link to the API.
* Track download tasks using the API.

## Disclaimer

- Intended to use only with videos that are under Creative Commons (CC) License

## ⚙ Quick Setup

1. Create Telegram bot using [BotFather](https://t.me/BotFather) and get your `token`
2. [Get your Telegram API Keys](https://my.telegram.org/apps) (`api_id` and `api_hash`)
3. [Find your Telegram User ID](https://stackoverflow.com/questions/32683992/find-out-my-own-user-id-for-sending-a-message-with-telegram-api)
4. Copy `app_bot/config-example.yml` to `app_bot/config.yml`
5. Write `token`, `api_id`, `api_hash` to `app_bot/config.yml` by changing respective
   placeholders
6. Write your Telegram user or group ID to the `allowed_users` -> `id` by replacing dummy
   value and change `forward_group_id` value if you want to forward the video to
   some group/channel when upload is enabled. Bot should be added to the group/channel to be able to send messages.
7. Change download media type for the user/group: `AUDIO`, `VIDEO` or `AUDIO_VIDEO`
   in `app_bot/config.yml`'s variable `download_media_type`. Default `VIDEO`
8. If you want your downloaded audio/video to be uploaded back to the Telegram, set `upload_video_file` config variable 
   for your user/group in the `app_bot/config.yml` to `True`
9. Media `STORAGE_PATH` environment variable is located in
   the `envs/worker.env` file. By default, it's `/filestorage` path inside the
   container. What you want is to map the real path to this inside
   the `docker-compose.yml` file for `worker` service, e.g. if you're on Windows, next
   strings mean container path `/filestorage` is mapped to real `D:/Videos` so your
   videos will be saved to your `Videos` folder.
   ```yml
     worker:
       volumes:
         - "D:/Videos:/filestorage"
   ```
10. Change application's `LOG_LEVEL` in `envs/common.env` to `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` if needed

## 🏃 Run

```bash
# Build base image
docker compose build base-image

# Build and run all services in detached mode
docker compose up --build -d -t 0 && docker compose logs --tail 100 -f

# Stop all services
docker compose stop -t 0
```

Your Telegram Bot should send you a startup message:
`✨ <YOUR_BOT_NAME> started, paste a video URL(s) to start download` and that's it. After
pasting video URL(s) bot will send you appropriate message whether they were downloaded
or something went wrong.

## 🐳 Run the pre-built images

The [`Docker images`](.github/workflows/docker-images.yml) workflow builds the three
service images on every push to `main` and on every `v*` tag, and publishes them to the
GitHub Container Registry:

| Image                                | Service                    |
|--------------------------------------|----------------------------|
| `ghcr.io/tuxflo/yt-dlp-bot/bot`      | Telegram bot               |
| `ghcr.io/tuxflo/yt-dlp-bot/worker`   | Downloader                 |
| `ghcr.io/tuxflo/yt-dlp-bot/api`      | API                        |

Tags are `latest` (the default branch), the version for release tags (`v1.8.0` is
published as `1.8.0`), and `sha-<short_commit>` for every build.

Steps 1-9 of the [Quick Setup](#-quick-setup) are still needed: you need your own
`app_bot/config.yml` and the `envs/` files, so clone the repository, then run the
services from the published images instead of building them:

```bash
# Pull and run everything
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d && docker compose -f docker-compose.ghcr.yml logs --tail 100 -f

# Pin a version instead of following 'latest'
YT_IMAGE_TAG=1.8.0 docker compose -f docker-compose.ghcr.yml up -d
```

Notes:

- **After the first workflow run, make the packages public**, otherwise `docker pull`
  asks for credentials. Go to your GitHub profile → *Packages* → select the package →
  *Package settings* → *Change visibility* → *Public*. Alternatively keep them private
  and `docker login ghcr.io -u <user>` with a personal access token that has the
  `read:packages` scope.
- `app_bot/config.yml` holds your Telegram credentials and is not committed, so it is
  **not** baked into the published bot image. `docker-compose.ghcr.yml` mounts it into
  the container at runtime instead.
- Images are built for `linux/amd64`. To also publish `linux/arm64` (Raspberry Pi, ARM
  NAS), the workflow needs `docker/setup-qemu-action` and `docker buildx build
  --platform linux/amd64,linux/arm64 --push`; note that emulated builds take
  considerably longer.
- If you forked this repository under a different account, the image prefix follows your
  fork automatically in the workflow. For `docker-compose.ghcr.yml` set
  `YT_IMAGE_PREFIX=ghcr.io/<your_user>/yt-dlp-bot`.

## 📺 Download a whole series, season or playlist

Send the link to the series/season/playlist page prefixed with the `/series` command
(`/season` and `/playlist` do the same):

```
/series https://arte.tv/de/videos/RC-027708/happy-valley
```

The worker resolves the link into the single videos behind it and queues every one of
them as its own download task, so each episode is reported, stored and uploaded
separately. Nested collections are flattened, so the example above queues all 18
episodes of all 3 seasons.

Notes:

- Without the command a series link is downloaded as a single video (the first entry),
  which is the previous behaviour of the bot.
- At most `MAX_PLAYLIST_ITEMS` videos (default `100`, see `envs/worker.env`) are queued
  from one link. You're told in the reply when the limit truncated the list.
- Several links can be passed at once: `/series <URL_1> <URL_2>`.
- Downloads run with the configured `MAX_SIMULTANEOUS_DOWNLOADS` limit, so a long series
  is downloaded gradually and not all at once.

### Failed episodes

A failed download is re-queued automatically after `RESEND_DELAY_MS` (default 60
seconds), up to `CONSUMER_NUMBER_OF_RETRY` times (default 2) — three attempts in total.
Only after the last attempt fails is an error reported to Telegram, so a video that
succeeds on the second try is never reported as broken. Both variables live in
`envs/common.env`.

If an episode still fails after that, **send the same series link again**. Entries that
were already downloaded, or that are still queued, are skipped, so only what is actually
missing gets downloaded:

```
📺 Happy Valley
🔢 18 videos found
⏭️ 15 already downloaded, skipped
⬇️ 3 queued
⏳ Each video is downloaded as a separate task.
```

Notes:

- Skipping is based on the task history in the database, matched on the exact episode
  URL. Users configured with `save_to_database: !!bool False` have their tasks purged,
  so for them nothing is ever skipped and re-sending downloads the whole series again.
- Only *failed* entries are re-queued. Entries still `PENDING` or `PROCESSING` are
  skipped too, so re-sending a link while the first run is still going does not queue
  the same video twice.
- To deliberately download something again, send the single video URL instead. A plain
  link is always downloaded and never checked against the history.

## 💻 Advanced setup

1. If you want to change `yt-dlp` download options, go to the `app_worker/ytdl_opts`
   directory, copy content from `default.py` to `user.py` and modify as you wish by
   checking [available options](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L180).
2. Default max simultaneous video downloads by worker service is 2. Change
   the `MAX_SIMULTANEOUS_DOWNLOADS` variable in `envs/worker.env` to desired value but
   keep in mind that default mounted volume size is 7168m (7GB) in `docker-compose.yml`
   so it may be not enough if you download a lot of large videos at once.
3. `yt-dlp` will try to download video thumbnail if it exists. In other case Worker
   service (particularly the FFmpeg process) will make a JPEG thumbnail from the
   video. It's needed when you choose to upload the video to the Telegram chat. By
   default, it will try to make it on the 10th second of the video, but if the video is
   shorter, it will make it on `video length / 2` time point because the FFmpeg process
   will error out. Change the `THUMBNAIL_FRAME_SECOND` variable if needed in
   the `envs/worker.env` file.
4. Max upload file size for non-premium Telegram user is 2GB (2147483648 bytes) which is
   reflected in the example config `app_bot/config-example.yml`. If the configured user
   is the premium user, you're allowed to upload files up to 4GB (4294967296 bytes) and
   can change the default value stored in the `upload_video_max_file_size` config
   variable.
5. If the website you want to download from requires authentication you can use your cookies by putting them into
   the `app_worker/cookies/cookies.txt` file in the Netscape format.
6. Maximum number of videos queued from a single `/series` link is 100. Change
   the `MAX_PLAYLIST_ITEMS` variable in `envs/worker.env` to desired value.
7. On NixOS run `nix-shell` in the repository root to get `ruff`, `uv`, `yt-dlp` and
   `ffmpeg` for linting (`ruff check .`, `ruff format --diff .`) and local debugging.

## 🛑 Failed download

If your URL can't be downloaded for some reason, you will see a message with error
details

![frames](.assets/download_failed.png)

## Access

- **API**: default port is `1984` and no auth. Port can be changed
  in `docker-compose.yml`
- **RabbitMQ**: default credentials are located in `envs/common.env`
- **PostgreSQL**: default credentials are located in `envs/common.env`.

## API

By default, API service will run on your `localhost` and `1984` port. API endpoint
documentations lives at `http://127.0.0.1:1984/docs`.

Note that a `POST /v1/tasks` request with `"playlist": true` creates one task per video
behind the link, none of which uses the task `id` returned by the request. Use
`GET /v1/tasks` to find them.

| Endpoint                                                           | Method   | Description                                                                                                                                |
|--------------------------------------------------------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `/status`                                                          | `GET`    | Get API healthcheck status, usually response is `{"status": "OK"}`                                                                         |
| `/v1/yt-dlp`                                                       | `GET`    | Get latest and currently installed `yt-dlp` version                                                                                        |
| `/v1/tasks/?include_meta=False&status=DONE`                        | `GET`    | Get all tasks with filtering options like to include large file metadata and by task status: `PENDING`, `PROCESSING`, `FAILED` and `DONE`. |
| `/v1/tasks/f828714a-5c50-45de-87c0-3b51b7e04039?include_meta=True` | `GET`    | Get info about task by ID                                                                                                                  |
| `/v1/tasks/latest?include_meta=True`                               | `GET`    | Get info about latest task                                                                                                                 |
| `/v1/tasks/f828714a-5c50-45de-87c0-3b51b7e04039`                   | `DELETE` | Delete task by ID                                                                                                                          |
| `/v1/tasks`                                                        | `POST`   | Create a download task by sending json payload `{"url": "<URL>"}`. Add `"playlist": true` to queue every video behind a series/playlist URL |
| `/v1/tasks/stats`                                                  | `GET`    | Get overall tasks stats                                                                                                                    |

### API examples

1. `GET http://localhost:1984/v1/tasks/?include_meta=False&status=DONE&limit=2&offset=0`

   Response
   ```json
   [
       {
           "id": "7ab91ef7-461c-4ef6-a35b-d3704fe28e6c",
           "url": "https://www.youtube.com/watch?v=PavYAOpVpJI",
           "status": "DONE",
           "source": "BOT",
           "added_at": "2022-02-14T02:29:55.981622",
           "created": "2022-02-14T02:29:57.211622",
           "updated": "2022-02-14T02:29:59.595551",
           "message_id": 621,
           "file": {
               "id": "4b1c63ed-3e32-43e6-a0b7-c7fc8713b268",
               "created": "2022-02-14T02:29:59.597839",
               "updated": "2022-02-14T02:29:59.597845",
               "name": "[Drone Freestyle] Mountain Landscape With Snow | Free Stock Footage | Creative Common Video",
               "ext": "mp4"
           }
       }
   ]
   ```
2. `POST http://localhost:1984/v1/tasks`

   Request
   ```json
   {
       "url": "https://www.youtube.com/watch?v=PavYAOpVpJI",
       "download_media_type": "AUDIO_VIDEO",
       "save_to_storage": false,
       "custom_filename": "cool.mp4",
       "automatic_extension": false,
       "playlist": false
   }
   ```
   Response
   ```json
   {
       "id": "5ac05808-b29c-40d6-b250-07e3e769d8a6",
       "url": "https://www.youtube.com/watch?v=PavYAOpVpJI",
       "source": "API",
       "added_at": "2022-02-14T00:35:25.419962+00:00"
   }
   ```
3. `GET http://localhost:1984/v1/tasks/stats`

   Response
   ```json
   {
       "total": 39,
       "unique_urls": 5,
       "pending": 0,
       "processing": 0,
       "failed": 26,
       "done": 13
   }
   ```
