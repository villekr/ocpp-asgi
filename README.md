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

This library is still in alpha state. I'm happy to discuss and help if you are considering the benefits of using this library in you project.

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

Central System is a collection of routes. You implement it by subclassing from ocpp_asti.ASGIApplication and overriding necessary methods to accommodate your needs.

```python
# central_system.py

class CentralSystem(ASGIApplication):
    """Central System is collection of routers."""
    ...

if __name__ == "__main__":
    central_system = CentralSystem()
    central_system.include_router(router)
    uvicorn.run(central_system, host="0.0.0.0", port=9000)
```

# Examples

Examples demonstrate how ocpp-asgi -library would be used in real life OCPP implementation. The following diagrams
show the system handling ocpp communication would be designed. Note that Client API implementation is not within scope
of ocpp-asgi library. Examples contain a one version how that could be implemented.

## ocpp-asgi standalone architecture

![ocpp-asgi standalone](/docs/ocpp-asgi_standalone.jpg)

## ocpp-asgi serverless architecture

![ocpp-asgi serverless](/docs/ocpp-asgi_serverless.jpg)

## ocpp-asgi serverless architecture AWS reference

![ocpp-asgi serverless AWS reference](/docs/ocpp-asgi_serverless_AWS.jpg)

## Running the examples

In order to run the examples clone the ocpp-asgi repository and install development dependencies. Poetry and pyenv are recommended. The following commands use poetry. Run commands e.g. in different terminal windows (or run the files within IDE).

First install the dependencies:
```
poetry install
```

There are two kind of examples showing how to use ocpp-asgi: standalone and serverless. Both examples use same ocpp action handlers (routers).

Run **Central System** either as standalone or serverless but not both!

### Central System (ocpp-asgi standalone)

Start Central System:
```
poetry run python ./examples/central_system/standalone/central_system.py
```

### Central System (ocpp-asgi serverless)

Of course when you run the example like this it's not really serverless. But deploying something central_system_http.py to e.g. AWS Lambda and running it with Mangum ASGI server is totally possible.

Start Central System HTTP backend:
```
poetry run python ./examples/central_system/serverless/central_system.py
```

Start Central System WebSocket proxy:
```
poetry run python ./examples/central_system/serverless/websocket_proxy.py
```

### Charging Station(s)

Run one of the following (or both if you like) to connect one or multiple charging stations.

Connect single Charging Station:
```
poetry run python ./examples/charging_station/connect_single.py
```

Connect multiple Charging Stations:
```
poetry run python ./examples/charging_station/connect_multiple.py
```

### Client API

Client API is a component that allows communication from Client application to Charging Station via Central System.
This example uses Redis as a channel here to decouple different components. You need docker and docker-compose to run this part.

Copy or rename .env_template to .env
```
cp examples/.env_template examples/.env
```

Start Redis with docker-compose
```
docker-compose -f examples/central_system/docker-compose.yaml up -d
```

Start Callback API:
```
poetry run python ./examples/central_system/apis/callback_api.py
```
Callback API swagger is available in http://localhost:9002/docs

Start Client API:
```
poetry run python ./examples/central_system/apis/client_api.py
```
Client API swagger is available in http://localhost:8080/docs

Now you may issue request from Client API to one of the connected Charging Stations. User charging_station_id 2, 3 or 4 unless you have modified the ids in the example. Note that example only supports to communicating with OCPP 2.0.1 protocol Charging Stations.