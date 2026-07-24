class YabkDumpError(Exception):
    pass


class UnauthorizedError(YabkDumpError):
    pass


class NetworkError(YabkDumpError):
    pass


class InvalidInputError(YabkDumpError):
    pass
