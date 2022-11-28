import asyncio

from charging_station import connect

from ocpp_asgi.router import Subprotocol


async def main():
    await asyncio.gather(
        connect(charging_station_id="1", subprotocol=Subprotocol.ocpp16),
        connect(charging_station_id="2", subprotocol=Subprotocol.ocpp201),
        connect(charging_station_id="3", subprotocol=Subprotocol.ocpp201),
    )


if __name__ == "__main__":
    asyncio.run(main())
