import os

import uvicorn
from aiohttp import ClientSession
from dotenv import load_dotenv
from loguru import logger

from examples.central_system.misc.channel import Pipe
from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.routers.v201.provisioning_router import (
    router as v201_provisioning_router,
)
from ocpp_asgi.app import ASGIApplication, HTTPEventContext, RouterContext

load_dotenv()

callback_api = os.getenv("CENTRAL_SYSTEM_CALLBACK_API_ENDPOINT_URL")
port = int(os.getenv("CENTRAL_SYSTEM_CALLBACK_API_ENDPOINT_PORT"))
base_url = f"{callback_api}:{port}/connections"


class CentralSystemHTTP(ASGIApplication):
    """Central System is collection of routers.

    Note that we don't handle on_connect, and on_disconnect events here at all
    """

    def __init__(self, pipe: Pipe):
        super().__init__()
        self.pipe: Pipe = pipe

    def http_parse_event(self, http_event: dict) -> HTTPEventContext:
        return HTTPEventContext(
            charging_station_id=http_event["requestContext"]["connection_id"],
            subprotocols=http_event["requestContext"]["subprotocols"],
            body=http_event["body"],
        )

    async def http_from_server_to_client(self, message: str, context: RouterContext):
        # Send event to http handler and if response is success then
        # send the response payload back to client.

        url = f"{base_url}/{context.charging_station_id}"
        async with ClientSession() as session:
            async with session.post(url, data=message) as resp:
                if resp.status != 200:
                    raise ValueError("Failure sending message from server to client.")

    async def consume_event(self, *, connection_id: str, message: str) -> str or None:
        try:
            value = await self.pipe.get(f"listen:{connection_id}")
            if value is not None:
                await self.pipe.send(connection_id, message)
                return None
        except Exception as e:
            logger.exception(e)
        return message


if __name__ == "__main__":
    pipe = Pipe()  # for sending Charging Stations responses to client api
    central_system = CentralSystemHTTP(pipe)
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    port = int(os.getenv("CENTRAL_SYSTEM_HTTP_ENDPOINT_PORT"))
    uvicorn.run(central_system, host="0.0.0.0", port=port, log_level="info")
