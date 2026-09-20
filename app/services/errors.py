"""Domain errors: services raise them, the API layer maps them to HTTP."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409
