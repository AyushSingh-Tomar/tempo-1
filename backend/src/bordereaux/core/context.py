"""Per-request context (request id, client ip, user agent, project) carried in
a ``ContextVar`` so services such as audit logging can enrich events without
every caller threading these values through explicitly.

Set by the request-context middleware in ``main.py``; outside a request
(tests, scripts, background work) the context is simply empty.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Iterator
from uuid import UUID


@dataclass(frozen=True)
class RequestContext:
    request_id: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    project_id: UUID | None = None


_EMPTY = RequestContext()
_request_context: ContextVar[RequestContext] = ContextVar("request_context", default=_EMPTY)


def get_request_context() -> RequestContext:
    return _request_context.get()


@contextmanager
def request_context(**values: object) -> Iterator[RequestContext]:
    """Temporarily overlay values onto the current request context."""
    ctx = replace(_request_context.get(), **values)  # type: ignore[arg-type]
    token = _request_context.set(ctx)
    try:
        yield ctx
    finally:
        _request_context.reset(token)


def set_request_context(ctx: RequestContext):  # returns a reset token
    return _request_context.set(ctx)


def reset_request_context(token) -> None:
    _request_context.reset(token)
