from dataclasses import asdict
from typing import Any
from uuid import uuid4

import ocpp.v16.call as call
import ocpp.v16.call_result as call_result
import pytest
from asgi_tools.tests import ASGITestClient
from ocpp.charge_point import camel_to_snake_case, remove_nones, snake_to_camel_case
from ocpp.messages import Call, CallResult, unpack, validate_payload

from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.standalone.central_system import CentralSystem


def payload_to_message(*, payload: Any, is_call_result: bool = False) -> str:
    camel_case_payload = snake_to_camel_case(asdict(payload))
    if is_call_result:
        operation = CallResult(
            unique_id=str(uuid4()),
            action=payload.__class__.__name__[:-7],
            payload=remove_nones(camel_case_payload),
        )
        msg = operation.to_json()
        return msg
    else:
        operation = Call(
            unique_id=str(uuid4()),
            action=payload.__class__.__name__[:-7],
            payload=remove_nones(camel_case_payload),
        )
        msg = operation.to_json()
        return msg


def message_to_payload(
    *, message: str, action: str, is_call_result: bool = True
) -> Any:
    response = unpack(message)
    response.action = action
    validate_payload(response, "1.6")
    snake_case_payload = camel_to_snake_case(response.payload)
    if is_call_result:
        cls = getattr(call_result, f"{action}Payload")
    else:
        cls = getattr(call, f"{action}Payload")
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
        # CS -> [Authorize request] -> Central System
        msg = payload_to_message(payload=call.AuthorizePayload(id_tag="dummy"))
        await ws.send(msg)

        # CS <- [Authorize response] <- Central System
        msg = await ws.receive()
        response = message_to_payload(message=msg, action="Authorize")
        assert type(response) == call_result.AuthorizePayload
