<div align="center">

```

                __    __             __                    
   __  ______ _/ /_  / /__      ____/ /_  ______ ___  ____ 
  / / / / __ `/ __ \/ //_/_____/ __  / / / / __ `__ \/ __ \
 / /_/ / /_/ / /_/ / ,< /_____/ /_/ / /_/ / / / / / / / /_/ /
 \__, /\__,_/_.___/_/|_|      \__,_/\__,_/_/ /_/ /_/ .___/ 
/____/                                            /_/      
```

</div>

Look up info or download books from [books.yandex.ru](https://books.yandex.ru) — no account needed for metadata, Yandex Plus to download.

Compatible with macOS and Linux. On Windows, use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).

## Quick start

```bash
uv tool install yabk-dump
yabk-dump
```

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

## What happens when you run it

You get a menu with two options:

### Download book

The tool walks you through the usual steps:

1. **Paste the book URL** — the ID is extracted automatically.
2. **Session ID** — grabbed from Chrome via `pycookiecheat` if available. Falls back to manual paste or `SESSION_ID` env variable.
3. **Output folder** — defaults to `~/Downloads/yandex_books`.
4. **Processing options** — download, strip CSS, pack into `.epub`, and optionally delete the source files after.

Result lands next to the output directory (e.g. `~/Downloads/yandex_books.epub`).

### About book

No auth needed. Paste a book URL and the tool fetches its metadata:

title, authors, translators, language, publication date, annotation, editor's notes, reader and bookshelf counts — straight from the Yandex public API. Handy for a quick look without downloading anything.

## Manual session ID

If automatic cookie extraction fails:

1. Log into [books.yandex.ru](https://books.yandex.ru) in your browser.
2. Open Developer Tools (`F12`), go to **Application** > **Cookies** > `https://books.yandex.ru`.
3. Copy the value of `Session_id`.

You can also export it as an environment variable to skip the prompt entirely:

```bash
export SESSION_ID="your-session-id-here"
yabk-dump
```

## Building from source

```bash
git clone https://github.com/levkovichm/yabk-dump
cd yabk-dump
uv sync
uv run yabk-dump
```

## Why strip CSS?

Yandex books embed inline styles that some EPUB readers render poorly. Clearing them leaves a clean document that you can reformat with [Calibre](https://calibre-ebook.com/) or your preferred reader.

## Related

- [Calibre](https://calibre-ebook.com/) — cross-platform ebook management and format conversion

Inspired by [bookmate_downloader](https://github.com/ilyakharlamov/bookmate_downloader).
