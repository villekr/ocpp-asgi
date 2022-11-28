import asyncio

from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.routers.v201.provisioning_router import (
    router as v201_provisioning_router,
)
from ocpp_asgi.app import ASGIApplication, RouterContext, Subprotocol


class CentralSystem(ASGIApplication):
    """Central System is collection of routers."""

    async def on_startup(self):
        print("(CentralSystem) Startup.")

    async def on_shutdown(self):
        print("(CentralSystem) Shutdown.")

    async def on_connect(self, context: RouterContext) -> bool:
        print(
            f"(CentralSystem) Charging Station id: {context.charging_station_id} subprotocol: {context.subprotocol} connected."  # noqa: E501
        )
        # You can inspect context.scope["headers"] and perform e.g. basic authentication
        allow_connection = True

        if allow_connection:
            # Create task for running any logic that happens during connection set up
            # The reasoning is that response from on_connect is quick and then allows
            # processing to continue in central system
            asyncio.create_task(self.after_on_connect(context))
        return allow_connection

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        print(
            f"(CentralSystem) Charging Station id: {charging_station_id} subprotocol: {subprotocol} disconnected. Reason code: {code}"  # noqa: E501
        )

    async def after_on_connect(self, context: RouterContext):
        # Put any connection set up related logic here
        pass


if __name__ == "__main__":
    import uvicorn

    central_system = CentralSystem()
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    uvicorn.run(central_system, host="0.0.0.0", port=9000)
