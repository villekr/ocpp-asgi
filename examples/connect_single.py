import asyncio

from charging_station import connect

from ocpp_asgi.router import Subprotocol


async def main():
    await asyncio.gather(
        connect(charging_station_id="4", subprotocol=Subprotocol.ocpp16),
    )


if __name__ == "__main__":
    asyncio.run(main())
