from dataclasses import asdict
from typing import Any
from uuid import uuid4

from ocpp.charge_point import camel_to_snake_case, remove_nones, snake_to_camel_case
from ocpp.messages import Call, CallError, CallResult, unpack, validate_payload
from ocpp.v16 import call as v16call
from ocpp.v16 import call_result as v16call_result
from ocpp.v20 import call as v20call
from ocpp.v20 import call_result as v20call_result
from ocpp.v201 import call as v201call
from ocpp.v201 import call_result as v201call_result

from ocpp_asgi.app import OCPPVersion


def create_call_error(message: str) -> str:
    """Create CallError serialized representation based on serialize Call.

    Raises ValueError if message is not type Call. CallResult and CallError
    don't require response.
    """
    call: Call = unpack(message)
    if isinstance(call, Call):
        call_error: CallError = call.create_call_error(None)
        return call_error.to_json()
    else:
        raise ValueError("message is not type Call")


def payload_to_operation(
    *, payload: Any, is_call_result: bool = False
) -> CallResult or Call:
    camel_case_payload = snake_to_camel_case(asdict(payload))
    if is_call_result:
        operation = CallResult(
            unique_id=str(uuid4()),
            action=payload.__class__.__name__[:-7],
            payload=remove_nones(camel_case_payload),
        )
        return operation
    else:
        operation = Call(
            unique_id=str(uuid4()),
            action=payload.__class__.__name__[:-7],
            payload=remove_nones(camel_case_payload),
        )
        return operation


def operation_to_message(operation: CallResult or Call) -> str:
    msg = operation.to_json()
    return msg


def payload_to_message(*, payload: Any, is_call_result: bool = False) -> str:
    operation = payload_to_operation(payload=payload, is_call_result=is_call_result)
    msg = operation.to_json()
    return msg


def message_to_payload(
    *, ocpp_version: str, message: str, action: str, is_call_result: bool = True
) -> Any:
    response = unpack(message)
    response.action = action
    validate_payload(response, ocpp_version)
    snake_case_payload = camel_to_snake_case(response.payload)
    if ocpp_version == OCPPVersion.v1_6.value:
        cls = (
            getattr(v16call_result, f"{action}Payload")
            if is_call_result
            else getattr(v16call, f"{action}Payload")
        )
    elif ocpp_version == OCPPVersion.v2_0.value:
        cls = (
            getattr(v20call_result, f"{action}Payload")
            if is_call_result
            else getattr(v20call, f"{action}Payload")
        )
    elif ocpp_version == OCPPVersion.v2_0_1.value:
        cls = (
            getattr(v201call_result, f"{action}Payload")
            if is_call_result
            else getattr(v201call, f"{action}Payload")
        )
    else:
        raise ValueError(f"Unsupport {ocpp_version}=")
    payload = cls(**snake_case_payload)
    return payload
