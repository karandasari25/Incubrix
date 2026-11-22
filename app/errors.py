from typing import Any

from fastapi import HTTPException


class APIError(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        retryable: bool = False,
        details: Any = None,
    ) -> None:
        super().__init__(status_code=status_code)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


def error_body(error: APIError) -> dict:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "details": error.details,
        }
    }

