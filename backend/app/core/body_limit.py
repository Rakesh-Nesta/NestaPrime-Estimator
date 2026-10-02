"""Request-body ceiling for the upload endpoints, applied BEFORE the framework parses the multipart body (FastAPI
parses -- and spools -- the whole form before a route handler runs, so a limit inside the handler comes too late).

  * a Content-Length above the route's ceiling is refused with 413 without reading the body;
  * a body with no Content-Length (chunked transfer) is counted as it arrives and cut off at the ceiling.

Ceilings: a chunk upload = MAX_CHUNK_BYTES + framing overhead; an ordinary upload / supersede = the 100 MB file
limit + framing overhead. Other routes are untouched."""

import json
import re

from app.core import upload_policy

_CHUNK = re.compile(r"^/attachments/upload-sessions/[^/]+/chunks/[^/]+$")
_ORDINARY = re.compile(r"^/attachments(?:/[^/]+/supersede)?$")


def _limit_for(method: str, path: str) -> int | None:
    if method != "POST":
        return None
    if _CHUNK.match(path):
        return upload_policy.MAX_CHUNK_BYTES + upload_policy.BODY_OVERHEAD_BYTES
    if _ORDINARY.match(path):
        return upload_policy.MAX_FILE_SIZE_BYTES + upload_policy.BODY_OVERHEAD_BYTES
    return None


class _TooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = _limit_for(scope["method"], scope["path"])
        if limit is None:
            return await self.app(scope, receive, send)

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True
            if too_big:
                return await self._refuse(send)

        received = 0
        exceeded = False
        started = False

        async def counting_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _TooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if exceeded:
                # The framework may have wrapped our cut-off into its own error (e.g. a 400 "error parsing the body");
                # whatever it tries to say, the answer is 413, sent once.
                if message["type"] == "http.response.start" and not started:
                    started = True
                    await self._refuse(send)
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            pass
        if exceeded and not started:
            await self._refuse(send)

    @staticmethod
    async def _refuse(send):
        body = json.dumps({"detail": "Request body is too large"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})
