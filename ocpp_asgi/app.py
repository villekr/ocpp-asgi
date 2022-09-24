import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List

from ocpp.messages import MessageType
from ocpp.v16 import call as v16_call
from ocpp.v16 import call_result as v16_call_result
from ocpp.v20 import call as v20_call
from ocpp.v20 import call_result as v20_call_result
from ocpp.v201 import call as v201_call
from ocpp.v201 import call_result as v201_call_result

from ocpp_asgi.asgi import (
    ASGIHTTPEvent,
    ASGILifeSpanEvent,
    ASGILifeSpanShutDown,
    ASGILifeSpanStartup,
    ASGIScope,
    ASGIWebSocketEvent,
    Receive,
    Scope,
    Send,
)
from ocpp_asgi.logging import log
from ocpp_asgi.router import OCPPAdapter, Router, RouterContext, Subprotocol

ocpp_adapters = {
    Subprotocol.ocpp201.value: OCPPAdapter(
        call=v201_call, call_result=v201_call_result, ocpp_version="2.0.1"
    ),
    Subprotocol.ocpp20.value: OCPPAdapter(
        call=v20_call, call_result=v20_call_result, ocpp_version="2.0"
    ),
    Subprotocol.ocpp16.value: OCPPAdapter(
        call=v16_call, call_result=v16_call_result, ocpp_version="1.6"
    ),
}


@dataclass
class HTTPEventContext:
    charging_station_id: str
    subprotocols: List[str]
    body: dict


@dataclass
class SendAdapter:
    send: Awaitable[Any]
    on_receive: Callable[[str, RouterContext], Awaitable[None]]
    http_from_server_to_client: Callable[[str, RouterContext], Awaitable[str]]
    scope: dict

    async def __call__(self, message: str, is_response: bool, context: RouterContext):
        if is_response:
            if self.scope["type"] == ASGIScope.websocket:
                await self.send(
                    {"type": ASGIWebSocketEvent.send.value, "text": message}
                )
            else:
                await self.send(
                    {"type": ASGIHTTPEvent.response_start.value, "status": 200}
                )
                await self.send(
                    {
                        "type": ASGIHTTPEvent.response_body.value,
                        "body": message.encode("utf-8"),
                    }
                )
        else:
            if self.scope["type"] == ASGIScope.websocket:
                await self.send(
                    {"type": ASGIWebSocketEvent.send.value, "text": message}
                )
            else:
                log.debug(f"<- HTTP: {context.charging_station_id=} {message=}")
                await self.http_from_server_to_client(message=message, context=context)


class ASGIApplication:
    """ASGI Application to handle event based message routing."""

    def __init__(self):
        self.routers: Router = {}

    def include_router(self, router: Router):
        self.routers[router.subprotocol] = router

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """ASGI signature handler.

        Args:
            scope (Scope): ASGI scope
            receive (Receive): ASGI handle for receiving messages
            send (Send): ASGI handle for sending messages
        """

        if scope["type"] in [ASGIScope.websocket, ASGIScope.http]:
            await self.handler(scope, receive, send)
        elif scope["type"] == ASGIScope.lifespan:
            await self.lifespan_handler(scope, receive, send)
        else:
            raise ValueError(f'Unsupported ASGI scope type: {scope["type"]}')

    async def lifespan_handler(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        event = await receive()
        if event["type"] == ASGILifeSpanEvent.startup.value:
            try:
                await self.on_startup()
                await send({"type": ASGILifeSpanStartup.complete.value})
            except Exception:
                await send({"type", ASGILifeSpanStartup.failed.value})
        elif event["type"] == ASGILifeSpanEvent.shutdown.value:
            try:
                await self.on_shutdown()
                await send({"type": ASGILifeSpanShutDown.complete.value})
            except Exception:
                await send({"type", ASGILifeSpanShutDown.failed.value})

    async def handler(self, scope: Scope, receive: Receive, send: Send):
        log.debug(f"{scope=}")
        while True:
            event = await receive()
            log.debug(f"{event=}")
            context: RouterContext = self._create_context(
                scope=scope, event=event, send=send
            )

            # WebSocket
            if event["type"] == ASGIWebSocketEvent.receive:
                await self.on_receive(message=context.body, context=context)
            elif event["type"] == ASGIWebSocketEvent.connect:
                response = await self.on_connect(context)
                if response:
                    await send({"type": "websocket.accept"})
                else:
                    await send({"type": "websocket.reject"})
            elif event["type"] == ASGIWebSocketEvent.disconnect:
                await self.on_disconnect(
                    charging_station_id=context.charging_station_id,
                    subprotocol=context.subprotocol,
                    code=event["code"],
                )
                break

            # HTTP
            elif event["type"] == ASGIHTTPEvent.request:
                if context is None:
                    await send(
                        {"type": ASGIHTTPEvent.response_start.value, "status": 400}
                    )
                    await send({"type": ASGIHTTPEvent.response_body.value})
                    break
                # TODO: handle more_body case
                message_type = int(context.body[1])
                if message_type != MessageType.Call:
                    # For "CallResult" and "CallError" send empty response back
                    # as ocpp protocol doesn't mandate response for these message types
                    # For "Call" response will be sent by router
                    await send(
                        {"type": ASGIHTTPEvent.response_start.value, "status": 200}
                    )
                    await send({"type": ASGIHTTPEvent.response_body.value})
                await self.on_receive(message=context.body, context=context)
            elif event["type"] == ASGIHTTPEvent.disconnect.value:
                break

    async def on_receive(self, *, message: str, context: RouterContext):
        router: Router = self.routers[context.subprotocol]
        try:
            await router.route_message(message=message, context=context)
        except Exception as e:
            log.error(f"Failure when processing message on_receive: {e=}")
            pass

    # Handlers to override in subclass

    async def on_startup(self):
        """ASGI lifecycle event"""
        pass

    async def on_shutdown(self):
        """ASGI lifecycle event"""
        pass

    async def on_connect(self, context: RouterContext) -> bool:
        """Invoked when websocket connection is being established.

        @return bool: True if connection is allowed, False if rejected.
        """
        return True

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        """Invoked when websocket connection is disconnected."""
        pass

    def http_parse_event(self, http_event: dict) -> HTTPEventContext:
        """Parse context and content from http event's body.

        Relevant only for HTTP central system.

        ASGI event will carry the content in event["body"].
        This is application specific adaptation how data is structured in body.
        """
        raise NotImplementedError

    async def http_from_server_to_client(self, message: str, context: RouterContext):
        """Handle sending message from http backend towards WebSocket proxy.

        Relevant only for HTTP central system.

        HTTP backend needs to send Call type messages to WebSocket proxy.
        This is application specific adaptation how this sending is done.
        """
        raise NotImplementedError

    # Private

    def _create_context(
        self, *, scope: Scope, event: dict, send: Send
    ) -> RouterContext or None:
        queue = asyncio.Queue()
        call_lock = asyncio.Lock()
        subprotocols: list[str] = []
        if scope["type"] == ASGIScope.websocket:
            charging_station_id = scope["path"].strip("/")
            subprotocols = scope["subprotocols"]
            body = event["text"] if "text" in event else None
        else:  # scope["type"] == ASGIScope.http:
            if event["type"] == ASGIHTTPEvent.disconnect:
                # Don't bother creating context for disconnect as it's not used
                return None
            if len(event["body"]) > 0:
                http_event = json.loads(event["body"])
                http_event_context: HTTPEventContext = self.http_parse_event(http_event)
                charging_station_id = http_event_context.charging_station_id
                subprotocols = http_event_context.subprotocols
                body = http_event_context.body

        if len(subprotocols) == 0:
            return None

        # Pick the highest matching subprotocol
        if Subprotocol.ocpp201 in subprotocols:
            subprotocol = Subprotocol.ocpp201.value
        elif Subprotocol.ocpp20 in subprotocols:
            subprotocol = Subprotocol.ocpp20.value
        elif Subprotocol.ocpp16 in subprotocols:
            subprotocol = Subprotocol.ocpp16.value
        else:
            raise ValueError

        send_adapter = SendAdapter(
            scope=scope,
            send=send,
            on_receive=self.on_receive,
            http_from_server_to_client=self.http_from_server_to_client,
        )
        context = RouterContext(
            scope=scope,
            # store parsed body to avoid parsing twice for on_action and after_action
            body=body,
            subprotocol=subprotocol,
            ocpp_adapter=ocpp_adapters[subprotocol],
            send=send_adapter,
            charging_station_id=charging_station_id,
            queue=queue,
            call_lock=call_lock,
        )
        return context
