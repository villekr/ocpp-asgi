import asyncio
import websockets

from ocpp_asgi.router import Subprotocol
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP16, call as call16, call_result as call_result16
import ocpp.v16.enums as ocpp_v16_enums
from ocpp.v201 import (
    ChargePoint as CP201,
    call as call201,
    call_result as call_result201,
)
import ocpp.v201.enums as ocpp_v201_enums


async def connect(id: str, subprotocol: Subprotocol):
    """Helper function to establish connection to Central System."""
    async with websockets.connect(
        f"ws://localhost:80/{id}", subprotocols=[subprotocol]
    ) as ws:
        if subprotocol == Subprotocol.ocpp16:
            cs = ChargingStation16(id, ws)
        elif subprotocol == Subprotocol.ocpp201:
            cs = ChargingStation201(id, ws)
        await asyncio.gather(cs.start(), cs.send_boot_notification())


class ChargingStation16(CP16):
    """Example charging station using ocpp 1.6 protocol."""

    async def send_boot_notification(self):
        print(
            f"(Charging Station) Charging Station id: {self.id} send_boot_notification"
        )
        request = call16.BootNotificationPayload(
            charge_point_model="Alpha", charge_point_vendor="Vendor"
        )

        response = await self.call(request)

        if response.status == ocpp_v16_enums.RegistrationStatus.accepted:
            print("(Charging Station) BootNotification accepted.")

    @on(ocpp_v16_enums.Action.GetLocalListVersion)
    async def on_get_local_list(self, **kwargs):
        print(f"(Charging Station) Charging Station id: {self.id} on_get_local_list")
        return call_result16.GetLocalListVersionPayload(list_version=0)


class ChargingStation201(CP201):
    """Example charging station using ocpp 2.0.1 protocol."""

    async def send_boot_notification(self):
        print(
            f"(Charging Station) Charging Station id: {self.id} send_boot_notification"
        )
        request = call201.BootNotificationPayload(
            charging_station={"model": "Alpha", "vendorName": "Vendor"},
            reason=ocpp_v201_enums.BootReasonType.power_up,
        )

        response = await self.call(request)

        if response.status == ocpp_v201_enums.RegistrationStatusType.accepted:
            print("(Charging Station) BootNotification accepted.")

    @on(ocpp_v201_enums.Action.GetLocalListVersion)
    async def on_get_local_list(self, **kwargs):
        print(f"(Charging Station) Charging Station id: {self.id} on_get_local_list")
        return call_result201.GetLocalListVersionPayload(version_number=0)


async def main():
    await asyncio.gather(
        connect(subprotocol=Subprotocol.ocpp16, id="charging_station_1"),
        connect(subprotocol=Subprotocol.ocpp201, id="charging_station_2"),
    )


if __name__ == "__main__":
    asyncio.run(main())
