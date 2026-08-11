import pytest

from yabk_dump.exc import (
    InvalidInputError,
    NetworkError,
    UnauthorizedError,
    YabkDumpError,
)


def test_yabk_dump_error_is_exception():
    assert issubclass(YabkDumpError, Exception)


def test_unauthorized_subclasses_yabk_dump_error():
    assert issubclass(UnauthorizedError, YabkDumpError)


def test_network_subclasses_yabk_dump_error():
    assert issubclass(NetworkError, YabkDumpError)


def test_invalid_input_subclasses_yabk_dump_error():
    assert issubclass(InvalidInputError, YabkDumpError)


def test_exceptions_carry_message():
    with pytest.raises(UnauthorizedError, match="session expired"):
        raise UnauthorizedError("session expired")
