import json

import uvicorn
from aiohttp import ClientSession

from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.routers.v201.provisioning_router import (
    router as v201_provisioning_router,
)
from ocpp_asgi.app import ASGIApplication, HTTPEventContext, RouterContext


class CentralSystemHTTP(ASGIApplication):
    """Central System is collection of routers.

    Note that we don't handle on_connect, and on_disconnect events here at all
    """

    def http_parse_event(self, http_event: dict) -> HTTPEventContext:
        return HTTPEventContext(
            charging_station_id=http_event["requestContext"]["connection_id"],
            subprotocols=http_event["requestContext"]["subprotocols"],
            body=http_event["body"],
        )

    async def http_from_server_to_client(self, message: str, context: RouterContext):
        # Send event to http handler and if response is success then
        # send the response payload back to client.
        url = f"http://localhost:8080/connections/{context.charging_station_id}"
        content = {"message": message}
        async with ClientSession() as session:
            # aiohttp discourages making session for every request...
            # So this code goes against the recommendation just to keep example simple
            async with session.post(url, data=json.dumps(content)) as resp:
                if resp.status != 200:
                    raise ValueError("Failure sending message from server to client.")


if __name__ == "__main__":
    central_system = CentralSystemHTTP()
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    uvicorn.run(central_system, host="0.0.0.0", port=80, log_level="info")
