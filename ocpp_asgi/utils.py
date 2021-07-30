from ocpp.messages import Call, CallError, unpack


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
