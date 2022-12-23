import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from ocpp.v201 import call, call_result

from examples.central_system.misc.utils import post_to_connection
from ocpp_asgi.app import OCPPVersion

load_dotenv()
app = FastAPI(title="OCPP-ASGI example client API")


@app.post(
    "/get-local-list-version/{charging_station_id}",
    response_model=call_result.GetLocalListVersionPayload,
    status_code=status.HTTP_200_OK,
    tags=["ocpp version 2.0.1"],
)
async def get_local_list_version(charging_station_id: str):
    # Note! This client api example currently handles only communication with
    # ocpp 2.0.1 version i.e. sending request with charging station using other
    # version of protocol will cause error in Charging Station
    payload = call.GetLocalListVersionPayload()
    try:
        response: call_result.GetLocalListVersionPayload = await post_to_connection(
            charging_station_id=charging_station_id,
            payload=payload,
            ocpp_version=OCPPVersion.v2_0_1,
        )
        return response
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="No response from Charging station",
        )


if __name__ == "__main__":
    port = int(os.getenv("CENTRAL_SYSTEM_CLIENT_API_PORT"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
