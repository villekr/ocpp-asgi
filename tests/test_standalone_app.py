from dataclasses import asdict
from typing import Any
from uuid import uuid4

import ocpp.v16.call_result as call_result
import pytest
from asgi_tools.tests import ASGITestClient
from ocpp.charge_point import camel_to_snake_case, remove_nones, snake_to_camel_case
from ocpp.messages import Call, unpack, validate_payload
from ocpp.v16.call import AuthorizePayload

from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.standalone.central_system import CentralSystem


def payload_to_message(payload: Any) -> str:
    camel_case_payload = snake_to_camel_case(asdict(payload))
    call = Call(
        unique_id=str(uuid4()),
        action=payload.__class__.__name__[:-7],
        payload=remove_nones(camel_case_payload),
    )
    msg = call.to_json()
    return msg


def message_to_payload(message: str, action: str) -> Any:
    response = unpack(message)
    response.action = action
    validate_payload(response, "1.6")
    snake_case_payload = camel_to_snake_case(response.payload)
    cls = getattr(call_result, f"{action}Payload")
    payload = cls(**snake_case_payload)
    return payload


@pytest.fixture
def standalone_app():
    central_system = CentralSystem()
    central_system.include_router(v16_provisioning_router)
    return central_system


@pytest.mark.asyncio
async def test_standalone_app(standalone_app):
    client = ASGITestClient(standalone_app)
    headers = {"Sec-WebSocket-Protocol": "ocpp1.6, ocpp2.0.1"}
    async with client.websocket(path="/123", headers=headers) as ws:
        msg = payload_to_message(AuthorizePayload(id_tag="dummy"))
        await ws.send(msg)
        msg = await ws.receive()
        response = message_to_payload(message=msg, action="Authorize")
        assert type(response) == call_result.AuthorizePayload
