from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode


class AppError(Exception):
    status_code = 400
    code = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_response(self, request_id: str) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "code": self.code.value,
                "message": self.message,
                "data": self.detail or None,
                "request_id": request_id,
            },
        )


class Unauthorized(AppError):
    status_code = 401
    code = ErrorCode.AUTH_UNAUTHORIZED


class BadCredentials(AppError):
    status_code = 401
    code = ErrorCode.AUTH_INVALID_CREDENTIALS


class UserExists(AppError):
    status_code = 409
    code = ErrorCode.AUTH_USER_EXISTS


class Forbidden(AppError):
    status_code = 403
    code = ErrorCode.RESOURCE_FORBIDDEN


class NotFound(AppError):
    status_code = 404
    code = ErrorCode.RESOURCE_NOT_FOUND


class Conflict(AppError):
    status_code = 409
    code = ErrorCode.RESOURCE_CONFLICT


class InvalidHealthData(AppError):
    status_code = 422
    code = ErrorCode.INVALID_HEALTH_DATA


class IllegalPlan(AppError):
    status_code = 422
    code = ErrorCode.INVALID_PLAN


class GraphError(AppError):
    status_code = 500
    code = ErrorCode.GRAPH_EXECUTION_ERROR


class FileRejected(AppError):
    status_code = 400
    code = ErrorCode.FILE_REJECTED


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "")
