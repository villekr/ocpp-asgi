from datetime import datetime

from loguru import logger
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, AuthorizationStatus, RegistrationStatus

from ocpp_asgi.router import HandlerContext, Router, Subprotocol

router = Router(subprotocol=Subprotocol.ocpp16)


@router.on(Action.BootNotification)
async def on_boot_notification(
    *, payload: call.BootNotificationPayload, context: HandlerContext
) -> call_result.BootNotificationPayload:
    id = context.charging_station_id
    logger.debug(f"(Central System) on_boot_notification Charging Station {id=}")
    # Do something with the payload...
    return call_result.BootNotificationPayload(
        current_time=datetime.utcnow().isoformat(),
        interval=10,
        status=RegistrationStatus.accepted,
    )


@router.after(Action.BootNotification)
async def after_boot_notification(
    *, payload: call.BootNotificationPayload, context: HandlerContext
):
    id = context.charging_station_id
    logger.debug(f"(Central System) after_boot_notification Charging Station {id=}")
    response = await context.send(call.GetLocalListVersionPayload())
    logger.debug(f"(Central System) Charging Station {id=} {response=}")


@router.on(Action.Authorize)
async def on_authorize(
    *, payload: call.AuthorizePayload, context: HandlerContext
) -> call_result.AuthorizePayload:
    logger.debug(f"(Central System) on_authorize Charging Station {id=}")
    response = call_result.AuthorizePayload(
        id_tag_info={"status": AuthorizationStatus.accepted}
    )
    return response
