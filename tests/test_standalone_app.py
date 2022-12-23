import ocpp.v16.call as call
import ocpp.v16.call_result as call_result
import pytest
from asgi_tools.tests import ASGITestClient
from dotenv import load_dotenv

from examples.central_system.misc.channel import Pipe, PubSub
from examples.central_system.routers.v16.provisioning_router import (
    router as v16_provisioning_router,
)
from examples.central_system.standalone.central_system import CentralSystem
from ocpp_asgi.utils import message_to_payload, payload_to_message

load_dotenv()


@pytest.fixture
def pubsub() -> PubSub:
    return PubSub()


@pytest.fixture
def pipe() -> Pipe:
    return Pipe()


@pytest.fixture
def standalone_app(pubsub, pipe):
    central_system = CentralSystem(pubsub=pubsub, pipe=pipe)
    central_system.include_router(v16_provisioning_router)
    return central_system


@pytest.mark.skip("Test runs successfully but hangs.")  # TODO: figure out
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
        response = message_to_payload(
            ocpp_version="1.6", message=msg, action="Authorize"
        )
        assert type(response) == call_result.AuthorizePayload
