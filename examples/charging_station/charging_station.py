import asyncio
import os
from base64 import b64encode

import ocpp.v16.enums as ocpp_v16_enums
import ocpp.v201.enums as ocpp_v201_enums
import websockets
from dotenv import load_dotenv
from loguru import logger
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP16
from ocpp.v16 import call as call16
from ocpp.v16 import call_result as call_result16
from ocpp.v201 import ChargePoint as CP201
from ocpp.v201 import call as call201
from ocpp.v201 import call_result as call_result201

from ocpp_asgi.router import Subprotocol

load_dotenv()


def basic_auth_header(username, password):
    assert ":" not in username
    user_pass = f"{username}:{password}"
    basic_credentials = b64encode(user_pass.encode()).decode()
    return "Authorization", f"Basic {basic_credentials}"


async def connect(*, charging_station_id: str, subprotocol: Subprotocol):
    """Helper function to establish connection to Central System."""
    endpoint = os.getenv("CENTRAL_SYSTEM_ENDPOINT_URL")
    port = os.getenv("CENTRAL_SYSTEM_ENDPOINT_PORT")
    url = f"{endpoint}:{port}/{charging_station_id}"
    async with websockets.connect(
        url,
        subprotocols=[subprotocol],
        extra_headers=[basic_auth_header("id", "pass123")],
    ) as ws:
        if subprotocol == Subprotocol.ocpp16:
            cs = ChargingStation16(charging_station_id, ws)
        elif subprotocol == Subprotocol.ocpp201:
            cs = ChargingStation201(charging_station_id, ws)
        await asyncio.gather(cs.start(), cs.send_boot_notification())


class ChargingStation16(CP16):
    """Example charging station using ocpp 1.6 protocol."""

    async def send_boot_notification(self):
        request = call16.BootNotificationPayload(
            charge_point_model="Alpha", charge_point_vendor="Vendor"
        )
        logger.debug(f"(Charging Station) {self.id=} -> {request=}")
        response: call_result16 = await self.call(request)
        logger.debug(f"(Charging Station) {self.id=} <- {response=}")

    @on(ocpp_v16_enums.Action.GetLocalListVersion)
    async def on_get_local_list(self, **kwargs):
        request = call16.GetLocalListVersionPayload(**kwargs)
        logger.debug(f"(Charging Station) {self.id=} <- {request=}")
        response = call_result16.GetLocalListVersionPayload(list_version=0)
        logger.debug(f"(Charging Station) {self.id=} -> {response=}")
        return response

    @on(ocpp_v16_enums.Action.RemoteStartTransaction)
    async def on_remote_start_transaction(self, **kwargs):
        request = call16.RemoteStartTransactionPayload(**kwargs)
        logger.debug(f"(Charging Station) {self.id=} <- {request=}")
        response = call_result16.RemoteStartTransactionPayload(
            status=ocpp_v16_enums.RemoteStartStopStatus.accepted.value
        )
        logger.debug(f"(Charging Station) {self.id=} -> {response=}")
        return response


class ChargingStation201(CP201):
    """Example charging station using ocpp 2.0.1 protocol."""

    async def send_boot_notification(self):
        request = call201.BootNotificationPayload(
            charging_station={"model": "Alpha", "vendorName": "Vendor"},
            reason=ocpp_v201_enums.BootReasonType.power_up,
        )
        logger.debug(f"(Charging Station) {self.id=} -> {request=}")
        response = await self.call(request)
        logger.debug(f"(Charging Station) {self.id=} <- {response=}")

    @on(ocpp_v201_enums.Action.GetLocalListVersion)
    async def on_get_local_list(self, **kwargs):
        request = call201.GetLocalListVersionPayload(**kwargs)
        logger.debug(f"(Charging Station) {self.id=} <- {request=}")
        response = call_result201.GetLocalListVersionPayload(version_number=0)
        logger.debug(f"(Charging Station) {self.id=} -> {response=}")
        return response

    @on(ocpp_v201_enums.Action.RequestStartTransaction)
    async def on_remote_start_transaction(self, **kwargs):
        request = call201.RequestStartTransactionPayload(**kwargs)
        logger.debug(f"(Charging Station) {self.id=} <- {request=}")
        response = call_result201.RequestStartTransactionPayload(
            status=ocpp_v201_enums.RequestStartStopStatusType.accepted.value
        )
        logger.debug(f"(Charging Station) {self.id=} -> {response=}")
        return response


async def main():
    await asyncio.gather(
        connect(charging_station_id="111", subprotocol=Subprotocol.ocpp16),
        connect(charging_station_id="222", subprotocol=Subprotocol.ocpp201),
    )


if __name__ == "__main__":
    asyncio.run(main())
