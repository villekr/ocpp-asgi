from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from typing import Callable, Any, Awaitable, Optional
from enum import Enum
import asyncio
import inspect
from dataclasses import dataclass, asdict
import logging
import uuid

from ocpp.charge_point import snake_to_camel_case, camel_to_snake_case, remove_nones
from ocpp.messages import Call, unpack, validate_payload, MessageType
from ocpp.exceptions import OCPPError, NotImplementedError

log = logging.getLogger("ocpp-asgi")


class Queue(ABC):
    """Queue interface for routing incoming CallResult/CallError."""

    @abstractmethod
    async def get(self) -> str:
        pass

    @abstractmethod
    def put_nowait(self, msg):
        pass


class Connection(ABC):
    """Connection interface for sending and receiving messages."""

    @abstractmethod
    async def send(self, message: str):
        pass

    @abstractmethod
    async def recv(self) -> str:
        pass


@dataclass
class OCPPAdapter:
    ocpp_version: str
    call: Awaitable[Any]
    call_result: Awaitable[Any]


class Subprotocol(str, Enum):
    ocpp16 = "ocpp1.6"
    ocpp20 = "ocpp2.0"
    ocpp201 = "ocpp2.0.1"


@dataclass
class RouterContext:
    """RouterContext class is passed to router."""

    charging_station_id: str
    subprotocol: Subprotocol
    connection: Connection
    ocpp_adapter: OCPPAdapter
    queue: Queue
    call_lock: Any  # asyncio.Lock()


@dataclass
class HandlerContext:
    """HandlerContext class instance is passed to handler."""

    charging_station_id: str

    # References to RouterContext and Router's call-method added here so that
    # we can send messages to specific Charging Station, which initiated messaging.
    _router_context: RouterContext
    _router: Router

    async def send(self, message: dataclass) -> Any:
        """Send message to Charging Station within action handler."""
        # Use a lock to prevent make sure that only 1 message can be send at a
        # a time.
        async with self._router_context.call_lock:
            return await self._router.call(
                message=message, context=self._router_context
            )


def subprotocol_to_ocpp_version(subprotocol: str):
    return subprotocol[4:]


class Router:
    """Router is a collection of ocpp action handlers."""

    subprotocol: Subprotocol = None

    def __init__(
        self,
        *,
        subprotocol: Subprotocol,
        response_timeout: Optional[int] = 30,
        create_task: bool = True,
    ):
        """Initialize Router instance.

        Args:
            subprotocol (Subprotocol): Defines the ocpp protocol version for this router
            response_timeout (int): When no response on a request is received
                within this interval, a asyncio.TimeoutError is raised.
            create_task (bool): Create asyncio.Task for executing
                "after"-handler. Does not affect "on-handler".
        """
        self.subprotocol = subprotocol

        # The maximum time in seconds it may take for a CP to respond to a
        # CALL. An asyncio.TimeoutError will be raised if this limit has been
        # exceeded.
        self._response_timeout = response_timeout

        # A dictionary that hooks for Actions. So if the CS receives a it will
        # look up the Action into this map and execute the corresponding hooks
        # if exists.
        # Dictionary contains the following structure for each Action:
        # {
        #     Action.BootNotification: {
        #         "_on_action": <reference to "on_boot_notification">,
        #         "_after_action": <reference to "after_boot_notification">,
        #         "_skip_schema_validation": False,
        #     },
        # }
        self._route_map = {}

        # Function used to generate unique ids for CALLs. By default
        # uuid.uuid4() is used, but it can be changed. This is meant primarily
        # for testing purposes to have predictable unique ids.
        self._unique_id_generator = uuid.uuid4

        # Use asyncio.create_task for "after"-handler.
        self._create_task = create_task
        self._response_queue = asyncio.Queue()

        # Dictionary for storing subscribers for, which are waiting for CallResult or
        # CallErrors.
        self.subscriptions = {}

    def on(self, action, *, skip_schema_validation=False):
        def decorator(func):
            @functools.wraps(func)
            def inner(*args, **kwargs):
                return func(*args, **kwargs)

            option = "_on_action"
            if action not in self._route_map:
                self._route_map[action] = {}
            self._route_map[action][option] = func
            self._route_map[action]["_skip_schema_validation"] = skip_schema_validation
            return inner

        return decorator

    def after(self, action):
        def decorator(func):
            @functools.wraps(func)
            def inner(*args, **kwargs):
                return func(*args, **kwargs)

            option = "_after_action"
            if action not in self._route_map:
                self._route_map[action] = {}
            self._route_map[action][option] = func
            return inner

        return decorator

    async def route_message(self, *, message: str, context: RouterContext):
        """
        Route a message received from a Charging Station.

        If the message is a of type Call the corresponding hooks are executed.
        If the message is of type CallResult or CallError the message is passed
        to the call() function via the response_queue.
        """
        try:
            msg = unpack(message)
        except OCPPError as e:
            log.exception(
                "Unable to parse message: '%s', it doesn't seem "
                "to be valid OCPP: %s",
                message,
                e,
            )
            return

        if msg.message_type_id == MessageType.Call:
            await self._handle_call(msg, context=context)

        elif msg.message_type_id in [
            MessageType.CallResult,
            MessageType.CallError,
        ]:
            if msg.unique_id in self.subscriptions:
                self.subscriptions[msg.unique_id].put_nowait(msg)

    async def _handle_call(self, msg, *, context: RouterContext = None):
        """
        Execute all hooks installed for based on the Action of the message.

        First the '_on_action' hook is executed and its response is returned to
        the client. If there is no '_on_action' hook for Action in the message
        a CallError with a NotImplemtendError is returned.

        Next the '_after_action' hook is executed.

        """
        ocpp_version = subprotocol_to_ocpp_version(self.subprotocol)

        try:
            handlers = self._route_map[msg.action]
        except KeyError:
            raise NotImplementedError(f"No handler for '{msg.action}' " "registered.")

        if not handlers.get("_skip_schema_validation", False):
            validate_payload(msg, ocpp_version)

        # OCPP uses camelCase for the keys in the payload. It's more pythonic
        # to use snake_case for keyword arguments. Therefore the keys must be
        # 'translated'. Some examples:
        #
        # * chargePointVendor becomes charge_point_vendor
        # * firmwareVersion becomes firmwareVersion
        snake_case_payload = camel_to_snake_case(msg.payload)

        try:
            handler = handlers["_on_action"]
        except KeyError:
            raise NotImplementedError(f"No handler for '{msg.action}' " "registered.")

        handler_context = HandlerContext(
            charging_station_id=context.charging_station_id,
            _router_context=context,
            _router=self,
        )
        try:
            try:
                response = handler(message=snake_case_payload, context=handler_context)
                if inspect.isawaitable(response):
                    response = await response
            except Exception as e:
                log.exception(e)
        except Exception as e:
            log.exception("Error while handling request '%s'", msg)
            response = msg.create_call_error(e).to_json()
            await self._send(response, context)

        temp_response_payload = asdict(response)

        # Remove nones ensures that we strip out optional arguments
        # which were not set and have a default value of None
        response_payload = remove_nones(temp_response_payload)

        # The response payload must be 'translated' from snake_case to
        # camelCase. So:
        #
        # * charge_point_vendor becomes chargePointVendor
        # * firmware_version becomes firmwareVersion
        camel_case_payload = snake_to_camel_case(response_payload)

        response = msg.create_call_result(camel_case_payload)

        if not handlers.get("_skip_schema_validation", False):
            validate_payload(response, ocpp_version)

        await self._send(response.to_json(), context=context)

        try:
            handler = handlers["_after_action"]
            response = handler(message=snake_case_payload, context=handler_context)
            if inspect.isawaitable(response):
                if self._create_task:
                    # Create task to avoid blocking when making a call
                    # inside the after handler
                    asyncio.ensure_future(response)
                else:
                    await response
        except KeyError:
            # '_on_after' hooks are not required. Therefore ignore exception
            # when no '_on_after' hook is installed.
            pass

    async def call(self, *, message: Any, context: RouterContext):
        ocpp_version = subprotocol_to_ocpp_version(self.subprotocol)

        camel_case_payload = snake_to_camel_case(asdict(message))

        call = Call(
            unique_id=str(self._unique_id_generator()),
            action=message.__class__.__name__[:-7],
            payload=remove_nones(camel_case_payload),
        )

        validate_payload(call, ocpp_version)

        await self._send(call.to_json(), context=context)
        self.subscriptions[call.unique_id] = context.queue
        try:
            response = await asyncio.wait_for(
                context.queue.get(), self._response_timeout
            )
        except asyncio.TimeoutError:
            del self.subscriptions[call.unique_id]
            raise

        if response.message_type_id == MessageType.CallError:
            log.warning("Received a CALLError: %s'", response)
            raise response.to_exception()
        else:
            response.action = call.action
            validate_payload(response, ocpp_version)

        snake_case_payload = camel_to_snake_case(response.payload)
        call_result = context.ocpp_adapter.call_result
        cls = getattr(call_result, message.__class__.__name__)
        return cls(**snake_case_payload)

    async def _send(self, message: str, context: RouterContext):
        log.info(f"{context.charging_station_id}: send {message}")
        await context.connection.send(message)
