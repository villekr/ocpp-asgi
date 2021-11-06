<p align="center">
<a href="https://github.com/villekr/ocpp-asgi/actions?query=workflow%3Amain" target="_blank">
    <img src="https://github.com/villekr/ocpp-asgi/workflows/main/badge.svg" alt="main">
</a>
<a href="https://codecov.io/gh/villekr/ocpp-asgi">
  <img src="https://codecov.io/gh/villekr/ocpp-asgi/branch/main/graph/badge.svg?token=DZ2QWVF3DX"/>
</a>
<a href="https://pypi.org/project/ocpp-asgi" target="_blank">
    <img src="https://img.shields.io/pypi/v/ocpp-asgi?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
</p>

---

# OCPP-ASGI

ocpp-asgi provides **ASGI compliant** interface for implementing **event-driven** **server-side** support for OCPP protocol with Python. It depends on and extends [mobilityhouse/ocpp](https://github.com/mobilityhouse/ocpp). 

The key features are:
* ASGI compliant interface supporting both WebSocket and HTTP protocols.
* Event-driven and "stateless" approach for implementing action handlers for OCPP messages. 
* Highly-scalable and supports serverless (e.g. AWS Lambda, Azure Functions) with compatible ASGI server.
* Requires small and straightforward changes from ocpp to action handlers (but is not backwards compatible).

Read the [blog post](https://ville-karkkainen.medium.com/towards-event-based-serverless-ocpp-backend-system-part-i-motivation-and-architecture-options-5d51ba09dfd6) about the motivation behind creating this library.

## Disclaimer!

This library is still in alpha state. At the moment I don't have time nor immediate business need to invest in further development. However, I'm happy to discuss and help if you are considering the benefits of using this library in you project.

Please send [email](mailto:ville.karkkainen@outlook.com) if you have any questions about this library or have some business inquiries in mind.

# Getting started

## Installation

```
pip install ocpp-asgi
```

Also ASGI server is required e.g. [uvicorn](https://www.uvicorn.org) or [mangum](https://www.uvicorn.org) when deployed to AWS Lambda with API Gateway.
```
pip install uvicorn
```

## Action handlers

Decorating OCPP message action handlers follows the similar approach as in ocpp-library. However, you don't need to define classes per OCPP protocol version. 

```python
# provisioning_router.py
from datetime import datetime

from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RegistrationStatus

from ocpp_asgi.router import HandlerContext, Router, Subprotocol

router = Router(subprotocol=Subprotocol.ocpp16)


@router.on(Action.BootNotification)
async def on_boot_notification(
    *, payload: call.BootNotificationPayload, context: HandlerContext
) -> call_result.BootNotificationPayload:
    id = context.charging_station_id
    print(f"(Central System) on_boot_notification Charging Station {id=}")
    # Do something with the payload...
    return call_result.BootNotificationPayload(
        current_time=datetime.utcnow().isoformat(),
        interval=10,
        status=RegistrationStatus.accepted,
    )
```

## Central System

Central System is a collection of routes. You implement it by subclassing from ocpp_asti.ASGIApplication and overriding necessary methods to accommodate your needs. Here's a minimal example using uvicorn.

```python
# central_system.py
import uvicorn
from provisioning_router import router
from ocpp_asgi.app import ASGIApplication, RouterContext, Subprotocol


class CentralSystem(ASGIApplication):
    """Central System is collection of routers."""


if __name__ == "__main__":
    central_system = CentralSystem()
    central_system.include_router(router)
    subprotocols = f"{Subprotocol.ocpp16}"
    headers = [("Sec-WebSocket-Protocol", subprotocols)]
    uvicorn.run(central_system, host="0.0.0.0", port=9000, headers=headers)
```

## Run the examples

In order to run the examples clone the ocpp-asgi repository and install dependencies. Poetry and pyenv are recommended.

There are two kind of examples how to implement central system with ocpp-asgi: standalone and serverless. Both examples use same ocpp action handlers (routers).

### Standalone example

Run the following commands e.g. in different terminal windows (or run the files within IDE).

Start Central System:
```
python ./examples/central_system/standalone/central_system.py
```

Start Charging Station:
```
python ./examples/charging_station.py
```

### Serverless example

Run the following commands in different terminal windows (or run the files within IDE). Of course when you run the example like this it's not really serverless. But deploying something central_system_http.py to e.g. AWS Lambda and running it with Mangum ASGI server is totally possible.

Start Central System HTTP backend:
```
python ./examples/central_system/serverless/central_system_http.py
```

Start Central System WebSocket proxy:
```
python ./examples/central_system/serverless/central_system_proxy.py
```

Start Charging Station:
```
python ./examples/charging_station.py
```