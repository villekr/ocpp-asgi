from datetime import datetime

from ocpp.v201 import call, call_result
from ocpp.v201.enums import Action, RegistrationStatusType

from ocpp_asgi.router import HandlerContext, Router, Subprotocol

router = Router(subprotocol=Subprotocol.ocpp201)


@router.on(Action.BootNotification)
async def on_boot_notification(
    *, payload: call.BootNotificationPayload, context: HandlerContext
) -> call_result.BootNotificationPayload:
    id = context.charging_station_id
    print(f"(Central System) on_boot_notification Charging Station {id=}")
    # Do something with the boot_notification...
    return call_result.BootNotificationPayload(
        current_time=datetime.utcnow().isoformat(),
        interval=10,
        status=RegistrationStatusType.accepted,
    )


@router.after(Action.BootNotification)
async def after_boot_notification(
    *, payload: call.BootNotificationPayload, context: HandlerContext
):
    id = context.charging_station_id
    print(f"(Central System) after_boot_notification Charging Station {id=}")
    response = await context.send(call.GetLocalListVersionPayload())
    print(f"(Central System) Charging Station {id=} {response=}")
