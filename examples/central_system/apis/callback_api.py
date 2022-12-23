import os

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, status
from loguru import logger

from examples.central_system.misc.channel import Envelope, PubSub

load_dotenv()
app = FastAPI(
    title="WebSocket Callback API (inspired by AWS API Gateway for WebSocket)"
)

PUBSUB_ID = os.getenv("CENTRAL_SYSTEM_PUPSUB_ID")
__pubsub = PubSub()


def pubsub_instance() -> PubSub:
    return __pubsub


@app.post(
    "/connections/{connection_id}",
    status_code=status.HTTP_200_OK,
)
async def post_connections(
    connection_id: str, payload: str = Body(), pubsub: PubSub = Depends(pubsub_instance)
):
    logger.debug(f"{payload=}")
    envelope: Envelope = Envelope(charging_station_id=connection_id, message=payload)
    await pubsub.publish(PUBSUB_ID, envelope.json())
    return None


if __name__ == "__main__":
    port = int(os.getenv("CENTRAL_SYSTEM_CALLBACK_API_ENDPOINT_PORT"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
