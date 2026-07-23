import logging
import os
import sys
from pathlib import Path

import questionary
from colorama import Fore, Style, init
from yandex_book import YandexBookClient

from yabk_dump.about import get_book_info
from yabk_dump.core import SERVICE_DOMAIN, BookClient, UnauthorizedError
from yabk_dump.search import search_book

init(autoreset=True)


class ColoramaFormatter(logging.Formatter):
    def format(self, record):
        record.levelname = f"{Fore.BLUE}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = ColoramaFormatter("%(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


ascii_logo = r"""
                __    __             __
   __  ______ _/ /_  / /__      ____/ /_  ______ ___  ____
  / / / / __ `/ __ \/ //_/_____/ __  / / / / __ `__ \/ __ \
 / /_/ / /_/ / /_/ / ,< /_____/ /_/ / /_/ / / / / / / /_/ /
 \__, /\__,_/_.___/_/|_|      \__,_/\__,_/_/ /_/ /_/ .___/
/____/                                            /_/
"""


def get_cookies():
    auth_cookie_name = "Session_id"
    if os.environ.get("SESSION_ID") is not None:
        session_id = os.environ.get("SESSION_ID")
    else:
        try:
            from pycookiecheat import chrome_cookies

            cc = chrome_cookies(f"https://{SERVICE_DOMAIN}")
            session_id = cc[auth_cookie_name]
        except Exception:
            session_id = input(
                f"Enter {auth_cookie_name} cookie\n"
                f"(Open browser DevTools → Application → Cookies → https://{SERVICE_DOMAIN}\n"
                f" find {auth_cookie_name} and copy its Value): "
            )
    return {auth_cookie_name: session_id}


def get_id_from_url(url: str) -> str:
    if not url:
        return None
    url = url.rstrip("/")
    parts = url.split("/")
    return parts[-1]


def main(bookurl: str, client: YandexBookClient) -> None:

    bookid = get_id_from_url(bookurl)
    book_data = get_book_info(client, bookid)
    print(
        f"\nTitle: {book_data.title}\n"
        f"UUID: {book_data.uuid}\n"
        f"Author(s): {book_data.authors}\n"
        f"Translator(s): {book_data.translators}\n"
        f"Language: {book_data.lang}\n"
        f"Year: {book_data.publication_date}\n"
        f"About: {book_data.about}\n"
        f"Editor's note: {book_data.editor_annotation}\n"
        f"Readers: {book_data.readers_count}\n"
        f"Bookshelves: {book_data.bookshelves_count}\n"
    )
    download_q = questionary.select(
        "Download this book?",
        choices=["yes", "no"],
    ).ask()
    if download_q == "yes":
        bookid = get_id_from_url(bookurl)

        outdir = questionary.text(
            "Output directory\n(Press Enter for default: ~/Downloads/yandex_books)"
        ).ask()
        if not outdir:
            outdir = str(Path.home() / "Downloads" / "yandex_books")

        download = questionary.select(
            "Download book content?",
            choices=["Yes", "No"],
        ).ask()

        del_css = questionary.select(
            "Clear CSS from files?",
            choices=["Yes", "No"],
        ).ask()

        make_epub = questionary.select(
            "Package as EPUB?",
            choices=["Yes", "No"],
        ).ask()

        del_downloaded = questionary.select(
            "Delete source files after packaging?",
            choices=["Yes", "No"],
        ).ask()
        print("\n")

        Path(outdir).mkdir(parents=True, exist_ok=True)

        client = BookClient(output_dir=outdir, cookies=get_cookies())
        book = client.get_book(book_id=bookid)
        if download == "Yes":
            book.run()
        if del_css == "Yes":
            book.clear_styles()
        if make_epub == "Yes":
            book.build_epub()
        if del_downloaded == "Yes":
            book.cleanup()
        text = f"""
    Book successfully downloaded!
    Source files are saved in: {outdir}

    For conversion to other formats and uploading to your ebook reader,
    we recommend Calibre — https://calibre-ebook.com/
        """
        logger.info(text)


def run():
    os.system("cls" if os.name == "nt" else "clear")
    try:
        print(ascii_logo)
        ya_client = YandexBookClient()
        action = questionary.select(
            "Select action:",
            choices=["Download", "Search"],
        ).ask()
        if action == "Download":
            bookurl = questionary.text(
                "Book URL\n(e.g. https://books.yandex.ru/book/KFHDG3bp/)"
            ).ask()
            main(bookurl, ya_client)
        elif action == "Search":
            s_query = questionary.text("Search by title:").ask()
            data = search_book(s_query, ya_client)
            items = list(data.items())
            for index, (title, vals) in enumerate(data.items()):
                print(f"{index} --- title: {title} --- author: {vals['author']}")
            select_book = int(input("Enter number: "))
            main(f"books.yandex.ru/{items[select_book][1]['id']}", ya_client)

        else:
            print("Unknown action, shutting down...")
            sys.exit()

    except KeyboardInterrupt:
        print("Cancelled.")
    except UnauthorizedError:
        logger.error(
            "Session_id cookie is invalid or expired.\n"
            "Please refresh it in your browser (DevTools → Application → Cookies → %s)\n"
            "or set the SESSION_ID environment variable.",
            f"https://{SERVICE_DOMAIN}",
        )
    except Exception:
        logger.exception("Unhandled error")
        print("Oops... An error occurred")


if __name__ == "__main__":
    run()
