import asyncio

try:
    from streamlit.server.Server import Server
except Exception:
    # Streamlit >= 0.65.0
    from streamlit.server.server import Server


def get_server_event_loop() -> asyncio.AbstractEventLoop:
    current_server = Server.get_current()
    return current_server._ioloop.asyncio_loop
