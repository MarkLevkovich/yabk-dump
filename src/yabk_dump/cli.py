import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import questionary
import rookiepy
from colorama import Fore, Style, init
from yandex_book import YandexBookClient

from yabk_dump.about import get_book_info
from yabk_dump.core import SERVICE_DOMAIN, BookClient
from yabk_dump.exc import InvalidInputError, UnauthorizedError
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
    session_id = None
    if os.environ.get("SESSION_ID") is not None:
        session_id = os.environ.get("SESSION_ID")
    else:
        try:
            cookies = rookiepy.chrome([SERVICE_DOMAIN, "yandex.ru"])
            for cc in cookies:
                if cc.get("name", "").lower() in ["session_id", "sessionid"]:
                    session_id = cc["value"]
        except Exception:
            session_id = input(
                f"Enter {auth_cookie_name} cookie\n"
                f"(Open browser DevTools → Application → Cookies → https://{SERVICE_DOMAIN}\n"
                f" find {auth_cookie_name} and copy its Value): "
            )
    return {auth_cookie_name: session_id}


def get_id_from_url(url: str) -> str | None:
    if not url:
        return None
    return urlparse(url).path.rstrip("/").split("/")[-1] or None


def main(bookurl: list[str], yclient: YandexBookClient) -> None:
    print("Download options:\n")
    outdir = questionary.text(
        "Output directory\n(Press Enter for default: ~/Downloads/yandex_books)"
    ).ask()
    if not outdir:
        outdir = str(Path.home() / "Downloads" / "yandex_books")

    del_css = questionary.select(
        "Clear CSS from files?",
        choices=["Yes", "No"],
    ).ask()

    make_epub = questionary.select(
        "Package as EPUB?",
        choices=["Yes", "No"],
    ).ask()

    del_downloaded = questionary.select(
        "Delete source files after packaging?\n",
        choices=["Yes", "No"],
    ).ask()
    _cookies = get_cookies()

    Path(outdir).mkdir(parents=True, exist_ok=True)
    for burl in bookurl:
        try:
            bookid = get_id_from_url(burl)
            if not bookid:
                continue
            book_data = get_book_info(yclient, bookid)
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
                client = BookClient(output_dir=outdir, cookies=_cookies)
                book = client.get_book(book_id=bookid)
                if download_q == "yes":
                    book.run()
                if del_css == "Yes":
                    book.clear_styles()
                if make_epub == "Yes":
                    book.build_epub()
                if del_downloaded == "Yes":
                    book.cleanup()
        except Exception:
            logger.error("An error has occurred")

    text = f"""
    Book(s) successfully downloaded!
    Source files are saved in: {outdir}

    For conversion to other formats and uploading to your ebook reader,
    we recommend Calibre — https://calibre-ebook.com/
        """
    logger.info(text)


def run():
    print("\033[H\033[J", end="")
    try:
        print(ascii_logo)
        ya_client = YandexBookClient()
        action = questionary.select(
            "Select action:",
            choices=["Download", "Search"],
        ).ask()
        if action == "Download":
            bookurl = questionary.text(
                "Enter book URL(s) separated by commas\n(e.g. https://books.yandex.ru/book/KFHDG3bp/)"
            ).ask()
            urls = bookurl.strip().split(",")
            main(urls, ya_client)
        elif action == "Search":
            s_query = questionary.text("Search by title:").ask()
            data = search_book(s_query, ya_client)
            items = list(data.items())
            if not items:
                print("Not found")
                sys.exit()
            pad = max((len(t) for t, _ in data.items()), default=0)  # max str len
            for index, (title, vals) in enumerate(data.items()):
                print(
                    f"  {Fore.CYAN}{index:>3}{Style.RESET_ALL}    "
                    f"{Fore.YELLOW}{title:<{pad}}{Style.RESET_ALL}    "
                    f"{Fore.GREEN}{vals['author']}{Style.RESET_ALL}"
                )
            try:
                select_book = int(input("Enter number: "))
            except ValueError:
                raise InvalidInputError("Please enter a number")
            if not 0 <= select_book < len(items):
                logger.error("Invalid selection")
                sys.exit()
            main([f"books.yandex.ru/{items[select_book][1]['id']}"], ya_client)
    except InvalidInputError as e:
        logger.error(e)
    except KeyboardInterrupt:
        logger.info("Cancelled.")
    except UnauthorizedError:
        logger.error(
            "Session_id cookie is invalid or expired.\n"
            "Please refresh it in your browser (DevTools → Application → Cookies → %s)\n"
            "or set the SESSION_ID environment variable.",
            f"https://{SERVICE_DOMAIN}",
        )
    except Exception:
        logger.exception("Unhandled error")


if __name__ == "__main__":
    run()
