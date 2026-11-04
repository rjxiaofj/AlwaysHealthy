from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode
from app.core.exceptions import request_id_of


def ok(request: Request, data: Any = None, message: str = "success") -> JSONResponse:
    return JSONResponse(
        content={
            "code": ErrorCode.SUCCESS.value,
            "message": message,
            "data": jsonable_encoder(data),
            "request_id": request_id_of(request),
        }
    )


def paged(request: Request, items: list[Any], total: int, page: int, page_size: int) -> JSONResponse:
    return ok(
        request,
        {
            "items": jsonable_encoder(items),
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )
