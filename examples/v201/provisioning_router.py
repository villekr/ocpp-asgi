from datetime import datetime

from ocpp_asgi.router import Router, HandlerContext, Subprotocol
from ocpp.v201.enums import Action, RegistrationStatusType
from ocpp.v201 import call, call_result


router = Router(subprotocol=Subprotocol.ocpp201)


@router.on(Action.BootNotification)
async def on_boot_notification(
    message: dict, context: HandlerContext
) -> call_result.BootNotificationPayload:
    id = context.charging_station_id
    print(f"(Central System) Charging Station id: {id} on_boot_notification")
    boot_notification = call.BootNotificationPayload(**message)
    # Do something with the boot_notification...
    return call_result.BootNotificationPayload(
        current_time=datetime.utcnow().isoformat(),
        interval=10,
        status=RegistrationStatusType.accepted,
    )


@router.after(Action.BootNotification)
async def after_boot_notification(message: dict, context: HandlerContext):
    id = context.charging_station_id
    print(f"(Central System) Charging Station id: {id} after_boot_notification")
    response = await context.send(call.GetLocalListVersionPayload())
    print(f"(Central System) Charging Station id: {id} response: {response}")
