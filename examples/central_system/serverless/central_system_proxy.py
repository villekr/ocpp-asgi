import asyncio
import json
from typing import Dict

import websockets
from aiohttp import ClientSession, web
from websockets import WebSocketServerProtocol

from ocpp_asgi.utils import create_call_error

routes = web.RouteTableDef()


class WebSocketProxy:
    """This Central System proxies the ocpp-j messages towards HTTP handler."""

    __singleton = None

    def __new__(cls):
        if not WebSocketProxy.__singleton:
            WebSocketProxy.__singleton = object.__new__(cls)
        return WebSocketProxy.__singleton

    def __init__(self):
        self.connections: Dict[WebSocketServerProtocol] = {}

    async def start(self):
        await asyncio.gather(self.start_websocket_server(), self.start_api_server())

    async def start_websocket_server(self):
        server = await websockets.serve(
            self.on_connect,
            host="localhost",
            port=9000,
            subprotocols=["ocpp2.0.1", "ocpp1.6"],
        )
        await server.wait_closed()

    async def start_api_server(self):
        app = web.Application()
        app.add_routes(
            [
                web.get("/connections/{connection_id}", self.get_connection),
                web.post("/connections/{connection_id}", self.post_connection),
                web.delete("/connections/{connection_id}", self.delete_connection),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 8080)
        await site.start()

        while True:
            await asyncio.sleep(3600)

    async def on_connect(self, websocket: WebSocketServerProtocol, path: str):
        connection_id = path.strip("/")
        print(f"on_connect CONNECT {connection_id=}")
        self.connections[connection_id] = websocket
        async for message in websocket:
            # Here we dispatch messages between Charging Station and HTTP handler
            print(f"-> WEBSOCKET: {connection_id=} {message=}")

            print(f"-> HTTP: {connection_id=} {message=}")
            response = await self.on_message(
                charging_station_id=connection_id,
                subprotocol=websocket.subprotocol,
                message=message,
            )
            if len(response) > 0:
                print(f"<- HTTP: {connection_id=} {response=}")
                await websocket.send(response)
                print(f"<- WEBSOCKET: {connection_id=} {response=}")
        print(f"on_connect DISCONNECT {connection_id=}")
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

            # Send event to http handler and if response is success then
            # send the response payload back to client.
            url = "http://localhost:80"

            async with session.post(url, data=json.dumps(proxy_event)) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    # If sending event to http handler failed then we must send ocpp
                    # call error type message back to client. This is necessary only if
                    # message type was Call.
                    # Note! This is different that error case, which happens when ocpp
                    # message is handled in http handler. In such case response payload
                    # is already CallError but we don't need to take care of it here.
                    try:
                        call_error: str = create_call_error(message)
                        return call_error
                    except ValueError:
                        pass

    # API methods to communicate from http backend to websocket client
    # Endpoints follow the design of AWS API Gateway for Websockets connections-API

    async def post_connection(self, request):
        connection_id = request.match_info["connection_id"]
        body = await request.json()
        message = body["message"]
        print(f"<- HTTP: {connection_id=} {message=}")
        if connection_id in self.connections:
            websocket: WebSocketServerProtocol = self.connections[connection_id]
            print(f"<- WEBSOCKET: {connection_id=} {message=}")
            await websocket.send(message)
            return web.Response()
        else:
            raise web.HTTPException(reason=f"{connection_id=} doesn't exist.")

    async def get_connection(self, request):
        connection_id = request.match_info["connection_id"]
        print(f"get_connection {connection_id=}")
        if connection_id in self.connections:
            return web.Response()
        else:
            raise web.HTTPException(reason=f"{connection_id=} doesn't exist.")

    async def delete_connection(self, request):
        connection_id = request.match_info["connection_id"]
        print(f"delete_connection {connection_id=}")
        if connection_id in self.connections:
            del self.connections[connection_id]
            return web.Response()
        else:
            raise web.HTTPException(reason=f"{connection_id=} doesn't exist.")


if __name__ == "__main__":
    asyncio.run(WebSocketProxy().start())
