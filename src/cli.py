import logging
import os
import pathlib
from core import YandexBook, BOOKS_DOMAIN
import questionary

logformat = "%(asctime)s (%(name)s) %(levelname)s %(module)s.%(funcName)s():%(lineno)d  %(message)s"
logging.basicConfig(level="INFO", format=logformat)


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
                f"Enter {auth_cookie_name} cookie\n(your browser -> developer tools -> application -> Cookies -> https://{BOOKS_DOMAIN} -> {auth_cookie_name} -> Value) :"
            )
    return {auth_cookie_name: session_id}


def run():
    bookid = questionary.text(
        "Book ID\n"
        "(from the book page URL, e.g. https://books.yandex.ru/book/KFHDG3bp/ -> KFHDG3bp)"
    ).ask()

    outdir = questionary.text(
        "Output directory\n(press Enter for default: ~/Downloads/yandex_books)"
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
        "Package as epub?",
        choices=["Yes", "No"],
    ).ask()

    del_downloaded = questionary.select(
        "Delete source files after packaging?",
        choices=["Yes", "No"],
    ).ask()

    if not os.path.exists(outdir):
        os.makedirs(outdir)

    yandex_book = YandexBook(outdir=outdir, cookies=get_cookies())
    book = yandex_book.get_book(bookid=bookid)
    if download:
        book.download()
    if del_css:
        book.delete_css()
    if make_epub:
        book.make_epub()
    if del_downloaded:
        book.delete_downloaded()


if __name__ == "__main__":
    run()
