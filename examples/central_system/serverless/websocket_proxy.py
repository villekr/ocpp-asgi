import asyncio
import json
import os
from typing import Dict

import websockets
from aiohttp import ClientSession, web
from dotenv import load_dotenv
from loguru import logger
from websockets import WebSocketServerProtocol

from examples.central_system.misc.channel import Envelope, PubSub
from ocpp_asgi.utils import create_call_error

load_dotenv()
routes = web.RouteTableDef()


class WebSocketProxy:
    """This Central System proxies the ocpp-j messages towards HTTP handler."""

    __singleton = None

    def __new__(cls):
        if not WebSocketProxy.__singleton:
            WebSocketProxy.__singleton = object.__new__(cls)
        return WebSocketProxy.__singleton

    def __init__(self):
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        http_endpoint = os.getenv("CENTRAL_SYSTEM_HTTP_ENDPOINT_URL")
        http_port = int(os.getenv("CENTRAL_SYSTEM_HTTP_ENDPOINT_PORT"))
        self.http_endpoint = f"{http_endpoint}:{http_port}"
        logger.debug(f"Central System {self.http_endpoint=}")
        self.pubsub: PubSub = pubsub

    async def start(self):
        await asyncio.gather(
            self.start_websocket_server(), self.receive_post_connections()
        )

    async def start_websocket_server(self):
        port = int(os.getenv("CENTRAL_SYSTEM_ENDPOINT_PORT"))
        server = await websockets.serve(
            self.on_connect,
            host="localhost",
            port=port,
            subprotocols=["ocpp2.0.1", "ocpp1.6"],
        )
        await server.wait_closed()

    async def on_connect(self, websocket: WebSocketServerProtocol, path: str):
        connection_id = path.strip("/")
        logger.debug(f"on_connect CONNECT {connection_id=}")
        self.connections[connection_id] = websocket
        async for message in websocket:
            # Here we dispatch messages between Charging Station and HTTP handler
            logger.debug(f"-> WEBSOCKET: {connection_id=} {message=}")

            logger.debug(f"-> HTTP: {connection_id=} {message=}")
            response = await self.on_message(
                charging_station_id=connection_id,
                subprotocol=websocket.subprotocol,
                message=message,
            )
            if len(response) > 0:
                logger.debug(f"<- HTTP: {connection_id=} {response=}")
                await websocket.send(response)
                logger.debug(f"<- WEBSOCKET: {connection_id=} {response=}")
        logger.debug(f"on_connect DISCONNECT {connection_id=}")
        if connection_id in self.connections:
            del self.connections[connection_id]

    async def on_message(
        self, *, charging_station_id: str, subprotocol: str, message: str
    ) -> str:
        # aiohttp discourages making session for every request...
        # So this code goes against the recommendation just to keep example simple
        async with ClientSession() as session:
            # It's up to us to decide the structure of http event. Parsing will
            # be implemented in http handler
            proxy_event = {
                "requestContext": {
                    "connection_id": charging_station_id,
                    "subprotocols": [subprotocol],
                },
                "body": message,
            }

            try:
                # Send event to http handler and if response is success then
                # send the response payload back to client.
                data = json.dumps(proxy_event)
                async with session.post(self.http_endpoint, data=data) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    else:
                        # If sending event to http handler failed then we must send ocpp
                        # call error type message back to client. This is necessary only
                        # if message type was Call.
                        # Note! This is different that error case, which happens when
                        # ocpp message is handled in http handler. In such case response
                        # payload is already CallError, but we don't need to take care
                        # of it here.
                        try:
                            call_error: str = create_call_error(message)
                            return call_error
                        except ValueError:
                            pass
            except Exception as e:
                logger.exception(e)

    # Functions for handling client api originated requests

    async def receive_post_connections(self):
        while True:
            try:
                value = await pubsub.subscribe(os.getenv("CENTRAL_SYSTEM_PUPSUB_ID"))
                envelope: Envelope = Envelope.parse_raw(value)
                if envelope.charging_station_id in self.connections:
                    connection: WebSocketServerProtocol = self.connections[
                        envelope.charging_station_id
                    ]
                    logger.debug(
                        f"(Central System) API Request {envelope.charging_station_id=} {envelope.message=}"  # noqa: E501
                    )
                    await connection.send(envelope.message)
            except Exception as e:
                logger.error(e)


if __name__ == "__main__":
    pubsub = PubSub()  # for receiving requests from client api to Charging Stations
    asyncio.run(WebSocketProxy().start())
