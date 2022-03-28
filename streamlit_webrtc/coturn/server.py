import logging
from streamlit.server.server import Server

from .turn import start_coturn_process, PORT

logger = logging.getLogger(__name__)


_COTURN_PROCESS_OBJECT_KEY = "__coturn__"


def start_coturn(
    listening_port: PORT,
    tls_listening_port: PORT,
    fingerprint: bool,
    lt_cred_mech: bool,
    server_name: str,
    realm: str,
    user: str,
):
    server = Server.get_current()

    if hasattr(server, _COTURN_PROCESS_OBJECT_KEY):
        logger.debug("The server already has the coturn process. Do nothing.")
    else:
        logger.debug("Start the coturn process.")
        p = start_coturn_process(
            listening_port=listening_port,
            tls_listening_port=tls_listening_port,
            fingerprint=fingerprint,
            lt_cred_mech=lt_cred_mech,
            server_name=server_name,
            realm=realm,
            user=user,
        )
        setattr(server, _COTURN_PROCESS_OBJECT_KEY, p)
