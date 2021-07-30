from dataclasses import asdict

import ocpp.v16.call as call_v16
import ocpp.v16.call_result as call_result_v16
import pytest
from ocpp.messages import Call, CallResult

from ocpp_asgi.utils import create_call_error


def test_create_call_error():
    payload = asdict(call_v16.HeartbeatPayload())
    call: Call = Call(unique_id=123, action="Heartbeat", payload=payload)
    message = call.to_json()
    call_error: str = create_call_error(message)
    assert type(call_error) is str


def test_create_call_error_invalid():
    payload = asdict(call_result_v16.StatusNotificationPayload())
    call_result: CallResult = CallResult(unique_id=123, payload=payload)
    message = call_result.to_json()
    with pytest.raises(ValueError):
        create_call_error(message)
