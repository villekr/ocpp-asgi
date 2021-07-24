import uvicorn

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
        # You can inspect context.scope["headers"] and perform eg. basic authentication
        return True

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        print(
            f"(CentralSystem) Charging Station id: {charging_station_id} subprotocol: {subprotocol} disconnected. Reason code: {code}"  # noqa: E501
        )


if __name__ == "__main__":
    central_system = CentralSystem()
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    subprotocols = f"{Subprotocol.ocpp201}, {Subprotocol.ocpp16}"
    headers = [("Sec-WebSocket-Protocol", subprotocols)]
    uvicorn.run(central_system, host="0.0.0.0", port=9000, headers=headers)
