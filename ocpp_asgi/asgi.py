from enum import Enum
from typing import Any, Awaitable, Callable, MutableMapping


class ASGIScope(str, Enum):
    lifespan = "lifespan"
    websocket = "websocket"
    http = "http"


class ASGILifeSpanEvent(str, Enum):
    startup = "lifespan.startup"
    shutdown = "lifespan.shutdown"


class ASGIWebSocketEvent(str, Enum):
    # receive
    connect = "websocket.connect"
    receive = "websocket.receive"
    disconnect = "websocket.disconnect"
    # send
    accept = "websocket.accept"
    send = "websocket.send"
    close = "websocket.close"


class ASGIHTTPEvent(str, Enum):
    disconnect = "http.disconnect"
    request = "http.request"
    response_start = "http.response.start"
    response_body = "http.response.body"


class ASGILifeSpanStartup(str, Enum):
    complete = "lifespan.startup.complete"
    failed = "lifespan.startup.failed"


class ASGILifeSpanShutDown(str, Enum):
    complete = "lifespan.shutdown.complete"
    failed = "lifespan.shutdown.failed"


Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGIAppSignature = Callable[[Scope, Receive, Send], Awaitable[None]]
