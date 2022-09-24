import asyncio

from ocpp.v16 import call as call16
from ocpp.v20 import call as call20
from ocpp.v201 import call as call201

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
            # Create task for running any logic that happens during connection setup
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
        # Example on how to send message to Charging Station e.g. after connection setup
        # Note! This is just an example, and it's not recommended to tie communication
        # towards Charging Station is on_connect event like this.
        await asyncio.sleep(1)  # Give Charging Station some time once connected
        if context.subprotocol == Subprotocol.ocpp16.value:
            message = call16.RemoteStartTransactionPayload(id_tag="abc")
            router = self.routers[context.subprotocol]
        elif context.subprotocol == Subprotocol.ocpp20.value:
            id_token = {"idToken": "abc", "type": "Central"}
            message = call20.RequestStartTransactionPayload(
                id_token=id_token, remote_start_id=123
            )
            router = self.routers[context.subprotocol]
        elif context.subprotocol == Subprotocol.ocpp201.value:
            id_token = {"idToken": "abc", "type": "Central"}
            message = call201.RequestStartTransactionPayload(
                id_token=id_token, remote_start_id=123
            )
            router = self.routers[context.subprotocol]
        else:
            raise ValueError(f"Unknown sub-protocol value: {context.subprotocol=}")
        try:
            response = await router.call(message=message, context=context)
            print(
                f"(Central System) Charging Station {context.charging_station_id} {response=}"  # noqa: E501
            )
        except Exception as e:
            print(
                f"(Central System) Failure sending message to Charging Station {context.charging_station_id} {e=}"  # noqa: E501
            )
            pass


if __name__ == "__main__":
    import uvicorn

    central_system = CentralSystem()
    central_system.include_router(v16_provisioning_router)
    central_system.include_router(v201_provisioning_router)
    subprotocols = f"{Subprotocol.ocpp201}, {Subprotocol.ocpp16}"
    headers = [("Sec-WebSocket-Protocol", subprotocols)]
    uvicorn.run(central_system, host="0.0.0.0", port=9000, headers=headers)
