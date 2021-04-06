from enum import Enum
import asyncio

from ocpp.v201 import call_result as v201_call_result, call as v201_call
from ocpp.v20 import call_result as v20_call_result, call as v20_call
from ocpp.v16 import call_result as v16_call_result, call as v16_call

from ocpp_asgi.router import Router, RouterContext, Connection, OCPPAdapter, Subprotocol

from typing import MutableMapping, Any, Callable, Awaitable

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class ASGIScope(str, Enum):
    lifecycle = "lifespan"
    websocket = "websocket"
    http = "http"


class ASGIEvent(str, Enum):
    startup = "lifespan.startup"
    shutdown = "lifespan.shutdown"
    receive = "websocket.receive"
    connect = "websocket.connect"
    disconnect = "websocket.disconnect"


ocpp_adapters = {
    Subprotocol.ocpp201: OCPPAdapter(
        call=v201_call, call_result=v201_call_result, ocpp_version="2.0.1"
    ),
    Subprotocol.ocpp20: OCPPAdapter(
        call=v20_call, call_result=v20_call_result, ocpp_version="2.0"
    ),
    Subprotocol.ocpp16: OCPPAdapter(
        call=v16_call, call_result=v16_call_result, ocpp_version="1.6"
    ),
}


class ASGIConnection(Connection):
    """Connection for sending and receiving messages."""

    def __init__(self, send: Send, receive: Receive):
        self._send = send
        # self._receive is not set as receive happens via ASGI interface

    async def send(self, message: str):
        await self._send({"type": "websocket.send", "text": message})

    async def recv(self) -> str:
        raise ValueError


def websocket_context(scope: Scope, receive: Receive, send: Send) -> RouterContext:
    charging_station_id = scope["path"].strip("/")
    subprotocols = scope["subprotocols"]
    # Pick the highest matching subprotocol
    if Subprotocol.ocpp201 in subprotocols:
        subprotocol = Subprotocol.ocpp201
    elif Subprotocol.ocpp20 in subprotocols:
        subprotocol = Subprotocol.ocpp20
    elif Subprotocol.ocpp16 in subprotocols:
        subprotocol = Subprotocol.ocpp16
    else:
        raise ValueError
    context = RouterContext(
        subprotocol=subprotocol,
        connection=ASGIConnection(send, receive),
        charging_station_id=charging_station_id,
        ocpp_adapter=ocpp_adapters[subprotocol],
        queue=asyncio.Queue(),
        call_lock=asyncio.Lock(),
    )
    return context


class Application:
    """ASGI Application to handle event based message routing."""

    def __init__(self):
        self.routers = {}

    def include_router(self, router: Router):
        self.routers[router.subprotocol] = router

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI signature handler.

        Args:
            scope (Scope): ASGI scope
            receive (Receive): ASGI handle for receiving messages
            send (Send): ASGI handle for sending messages
        """
        if scope["type"] == ASGIScope.lifecycle:
            await self._lifecycle_handler(scope, receive, send)
        elif scope["type"] == ASGIScope.websocket:
            await self._websocket_handler(scope, receive, send)
        elif scope["type"] == ASGIScope.http:
            await self._http_handler(scope, receive, send)
        else:
            raise ValueError(f'Unsupported ASGI scope type: {scope["type"]}')

    async def _lifecycle_handler(self, scope, receive, send):
        event = await receive()
        if event["type"] == ASGIEvent.startup.value:
            await self.on_startup()
            await send({"type": "lifespan.startup.complete"})
        elif event["type"] == ASGIEvent.shutdown.value:
            await self.on_shutdown()
            await send({"type": "lifespan.shutdown.complete"})

    async def _websocket_handler(self, scope, receive, send):
        connection = True
        while connection:
            event = await receive()
            context: RouterContext = websocket_context(scope, receive, send)
            if event["type"] == ASGIEvent.receive.value:
                if "text" not in event:
                    # OCPP-J message is never binary.
                    raise ValueError
                # Pass the message to correct router based subprotocol version
                router: Router = self.routers[context.subprotocol]
                await router.route_message(message=event["text"], context=context)
            elif event["type"] == ASGIEvent.connect.value:
                response = await self.on_connect(
                    charging_station_id=context.charging_station_id,
                    subprotocol=context.subprotocol,
                )
                if response:
                    await send({"type": "websocket.accept"})
                else:
                    await send({"type": "websocket.reject"})
            elif event["type"] == ASGIEvent.disconnect.value:
                await self.on_disconnect(
                    charging_station_id=context.charging_station_id,
                    subprotocol=context.subprotocol,
                    code=event["code"],
                )
                connection = False

    async def _http_handler(self, scope, receive, send):
        # ASGI http.request event type handling can be extended in subclasses
        # as interface between "Service" and "ASGI server" depends about
        # the used service (e.g. AWS).
        pass

    # Handlers to override in subclass

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass

    async def on_connect(
        self, *, charging_station_id: str, subprotocol: Subprotocol
    ) -> bool:
        """Invoked when websocket connection is being established.

        @return bool: True if connection is allowed, False if rejected.
        """
        pass

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        """Invoked when websocket connection is disconnected."""
        pass
