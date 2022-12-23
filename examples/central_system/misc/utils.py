import os
from typing import Any

import aiohttp
from dotenv import load_dotenv

from examples.central_system.misc.channel import Pipe
from ocpp_asgi.app import OCPPVersion
from ocpp_asgi.utils import message_to_payload, payload_to_message

load_dotenv()

callback_api = os.getenv("CENTRAL_SYSTEM_CALLBACK_API_ENDPOINT_URL")
port = os.getenv("CENTRAL_SYSTEM_CALLBACK_API_ENDPOINT_PORT")
base_url = f"{callback_api}:{port}/connections"

pipe: Pipe = Pipe()


async def post_to_connection(
    *, charging_station_id: str, payload: Any, ocpp_version: OCPPVersion
) -> Any:
    action: str = payload.__class__.__name__[:-7]
    message: str = payload_to_message(payload=payload, is_call_result=False)

    # 1) Post a request to callback api
    url: str = f"{base_url}/{charging_station_id}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=message) as resp:
            if resp.status != 200:
                raise Exception("Non-200 response")

    # 2) Wait for response via Pipe (redis)
    response_body = await pipe.listen(charging_station_id)

    # 3) Construct response payload, in this case just to OCPP response payload as JSON
    response = message_to_payload(
        ocpp_version=ocpp_version.value,
        message=response_body,
        action=action,
        is_call_result=True,
    )
    return response
