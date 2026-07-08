class UserFacingError(Exception):
    """Error that can be safely shown to the user without leaking internals."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ConfigurationError(UserFacingError):
    pass


class DocumentReadError(UserFacingError):
    pass


class AnalyzerError(UserFacingError):
    pass

