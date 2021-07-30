from ocpp_asgi.router import Subprotocol, subprotocol_to_ocpp_version


def test_subprotocol_to_ocpp_version():
    ocpp_version: str = subprotocol_to_ocpp_version(Subprotocol.ocpp16)
    assert ocpp_version == "1.6"
