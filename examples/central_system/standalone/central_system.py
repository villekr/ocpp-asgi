import asyncio
import os
from typing import TypedDict

import uvicorn
from dotenv import load_dotenv
from loguru import logger

from examples.central_system.misc.channel import Envelope, Pipe, PubSub
from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.routers.v201.provisioning_router import (
    router as v201_provisioning_router,
)
from ocpp_asgi.app import ASGIApplication, RouterContext, Subprotocol

load_dotenv()


class ContextDict(TypedDict):
    charging_station_id: str
    routerContext: RouterContext


class CentralSystem(ASGIApplication):
    """Central System is collection of routers."""

    def __init__(self, pubsub: PubSub, pipe: Pipe):
        super().__init__()
        self.contexts: ContextDict = {}
        self.pubsub: PubSub = pubsub
        self.pipe: Pipe = pipe

    async def on_startup(self):
        logger.debug("(CentralSystem) Startup.")
        asyncio.create_task(self.receive_post_connections())

    async def on_shutdown(self):
        logger.debug("(CentralSystem) Shutdown.")

    async def on_connect(self, context: RouterContext) -> bool:
        charging_station_id = context.charging_station_id
        subprotocol = context.subprotocol
        logger.debug(
            f"(CentralSystem) {charging_station_id=} {subprotocol=} connected."  # noqa: E501
        )
        # You can inspect context.scope["headers"] and perform e.g. basic authentication
        allow_connection = True

        if allow_connection:
            self.contexts[charging_station_id] = context
            # Create task for running any logic that happens during connection set up
            # The reasoning is that response from on_connect is quick and then allows
            # processing to continue in central system
            asyncio.create_task(self.after_on_connect(context))
        return allow_connection

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        logger.debug(
            f"(CentralSystem) {charging_station_id=} {subprotocol=} disconnected. Reason code: {code}"  # noqa: E501
        )
        del self.contexts[charging_station_id]

    async def after_on_connect(self, context: RouterContext):
        # Put any connection set up related logic here
        pass

    # Functions for handling client api originated requests

    async def receive_post_connections(self):
        while True:
            try:
                value = await pubsub.subscribe(os.getenv("CENTRAL_SYSTEM_PUPSUB_ID"))
                envelope: Envelope = Envelope.parse_raw(value)
                if envelope.charging_station_id in self.contexts:
                    context: RouterContext = self.contexts[envelope.charging_station_id]
                    logger.debug(
                        f"(Central System) API Request {envelope.charging_station_id=} {envelope.message=}"  # noqa:E501
                    )
                    await context.send(
                        message=envelope.message, is_response=False, context=context
                    )
            except Exception as e:
                logger.error(e)

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
    pubsub = PubSub()  # for receiving requests from client api to Charging Stations
    pipe = Pipe()  # for sending Charging Stations responses to client api
    central_system = CentralSystem(pubsub=pubsub, pipe=pipe)
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    port = int(os.getenv("CENTRAL_SYSTEM_ENDPOINT_PORT"))
    uvicorn.run(central_system, host="0.0.0.0", port=port, log_level="info")
