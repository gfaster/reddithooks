# RedditHooks

A program to send Reddit posts to Discord

---

## Setup:
- For each [webhook](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks), make sure there is a row added in `run_wait`
- The number in `run_wait` corresponds to how many times the program will run before posting to the corresponding webhook.
	- `1` means it will run every time.
- The subreddit *must* be an rss feed.
- In `config.json`, `request_pause` is the time between sending http requests
- In `config.json`, `db_file` is the name of the database file
	- make sure that it has the `.db` extension
	- there is no need to create this file, the program will do it on first run

---

## Building from source:
- Ensure Python and pip is installed.
- on Windows: run `build.bat`
- Mac OS and Linux: use PyInstaller to build and then copy `config.json` to `dist/`
- If neither sound fun, it is possible to simply run `main.py` using python