import logging
import os

FORMAT = "[%(funcName)s - %(lineno)s] %(message)s"
log = logging.getLogger("ocpp-asgi")
logging.basicConfig(format=FORMAT)
log.setLevel(os.getenv("LOGLEVEL", "INFO"))
