import logging
import os
import pathlib
from yabk_dump.core import YandexBook, BOOKS_DOMAIN
import questionary
from colorama import Fore, Style, init

init(autoreset=True)


class ColoramaFormatter(logging.Formatter):
    def format(self, record):
        record.levelname = f"{Fore.BLUE}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


logger = logging.getLogger()
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

            cc = chrome_cookies(f"https://{BOOKS_DOMAIN}")
            session_id = cc[auth_cookie_name]
        except Exception:
            session_id = input(
                f"Enter {auth_cookie_name} cookie\n"
                f"(Open browser DevTools → Application → Cookies → https://{BOOKS_DOMAIN}\n"
                f" find {auth_cookie_name} and copy its Value): "
            )
    return {auth_cookie_name: session_id}


def get_id_from_url(url: str) -> str:
    if not url:
        return None
    url = url.rstrip("/")
    parts = url.split("/")
    return parts[-1]


def run():
    try:
        print(ascii_logo)
        bookurl = questionary.text(
            "Book URL\n(e.g. https://books.yandex.ru/book/KFHDG3bp/)"
        ).ask()

        bookid = get_id_from_url(bookurl)

        outdir = questionary.text(
            "Output directory\n(Press Enter for default: ~/Downloads/yandex_books)"
        ).ask()
        if not outdir:
            outdir = str(pathlib.Path.home() / "Downloads" / "yandex_books")

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

        if not os.path.exists(outdir):
            os.makedirs(outdir)

        yandex_book = YandexBook(outdir=outdir, cookies=get_cookies())
        book = yandex_book.get_book(bookid=bookid)
        if download == "Yes":
            book.download()
        if del_css == "Yes":
            book.delete_css()
        if make_epub == "Yes":
            book.make_epub()
        if del_downloaded == "Yes":
            book.delete_downloaded()
        text = f"""
    Book successfully downloaded!
    Source files are saved in: {outdir}
    
    For conversion to other formats and uploading to your ebook reader,
    we recommend Calibre — https://calibre-ebook.com/
        """
        logger.info(text)
    except KeyboardInterrupt:
        print("Cancelled.")
    except Exception:
        logger.exception("Unhandled error")
        print("Oops... An error occurred")


if __name__ == "__main__":
    run()
