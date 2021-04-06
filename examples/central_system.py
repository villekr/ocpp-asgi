import uvicorn

from ocpp_asgi.app import Application, Subprotocol
from examples.v16.provisioning_router import router as v16_provisioning_router
from examples.v201.provisioning_router import router as v201_provisioning_router


class CentralSystem(Application):
    """Central System is collection of routers."""

    async def on_startup(self):
        print("(Central System) Startup.")

    async def on_shutdown(self):
        print("(Central System) Shutdown.")

    async def on_connect(
        self, *, charging_station_id: str, subprotocol: Subprotocol
    ) -> bool:
        print(
            f"(Central System) Charging Station id: {charging_station_id} subprotocol: {subprotocol} connected."
        )
        return True

    async def on_disconnect(
        self, *, charging_station_id: str, subprotocol: Subprotocol, code: int
    ):
        print(
            f"(Central System) Charging Station id: {charging_station_id} subprotocol: {subprotocol} disconnected. Reason code: {code}"
        )


if __name__ == "__main__":
    central_system = CentralSystem()
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    subprotocols = f"{Subprotocol.ocpp201}, {Subprotocol.ocpp16}"
    headers = [("Sec-WebSocket-Protocol", subprotocols)]
    uvicorn.run(central_system, host="0.0.0.0", port=80, headers=headers)
