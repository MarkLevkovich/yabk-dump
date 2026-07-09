<div align="center">

```
                __    __             __                    
   __  ______ _/ /_  / /__      ____/ /_  ______ ___  ____ 
  / / / / __ `/ __ \/ //_/_____/ __  / / / / __ `__ \/ __ \
 / /_/ / /_/ / /_/ / ,< /_____/ /_/ / /_/ / / / / / / /_/ /
 \__, /\__,_/_.___/_/|_|      \__,_/\__,_/_/ /_/ /_/ .___/ 
/____/                                            /_/      
```
</div>
Downloads books from [books.yandex.ru](https://books.yandex.ru) and saves them as epub.

You need **Yandex Plus** subscription — or the book must be free.

Works on macOS and Linux. Windows users — use WSL.

## Install

```bash
uv tool install yabk-dump
```

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

## Usage

```bash
yabk-dump
```

The program will walk you through:

1. **Book ID** — open the book on books.yandex.ru and copy the ID from the URL.  
   For `https://books.yandex.ru/book/KFHDG3bp/` the ID is `KFHDG3bp`.

2. **Session ID** — you'll be asked for it unless `pycookiecheat` can grab it from Chrome automatically.

   To get it manually:
   - Log into [books.yandex.ru](https://books.yandex.ru) in your browser.
   - Open Developer Tools (`F12`).
   - Go to **Application** → **Cookies** → `https://books.yandex.ru`.
   - Find `Session_id`, copy the value.

   You can also set the `SESSION_ID` environment variable to skip the prompt entirely.

3. **Where to save** — default is `~/Downloads/yandex_books`.

4. **What to do** — the CLI will ask step by step:
   - Download book content
   - Strip CSS from files (makes epub cleaner)
   - Package as `.epub`
   - Delete the raw files after packaging

The epub lands next to the output folder with the same name (e.g. `~/Downloads/yandex_books.epub`).

## From source

```bash
git clone https://github.com/levkovichm/yabk-dump
cd yabk-dump
uv sync
uv run yabk-dump
```

## Why would you strip CSS?

Yandex books come with a bunch of inline CSS that some epub readers handle poorly. Clearing it gives you a clean slate — you can then apply your own styles in Calibre or your reader of choice.

## Recommended tools

- [Calibre](https://calibre-ebook.com/) — book management, format conversion, editing.
