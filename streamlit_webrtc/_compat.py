import streamlit as st
from packaging import version

ST_VERSION = version.parse(st.__version__)

VER_GTE_1_12_0 = ST_VERSION >= version.parse("1.12.0")
""" Since 1.12.0, Streamlit has changed its internal architecture
creating new `web` and `runtime` submodules to which some files have been moved
decoupling the web server-related files and the core runtime,
e.g. https://github.com/streamlit/streamlit/pull/4956.

During this a huge refactoring, `Server._singleton` and
its accessor `Server.get_current()` have been removed
(https://github.com/streamlit/streamlit/pull/4966)
that we have been using as a server-wide global object,
so we have to change the way to access it.
"""

VER_GTE_1_12_1 = ST_VERSION >= version.parse("1.12.1")
""" Since 1.12.1, as a part of the decoupling of the runtime and the web server,
a large part of the `Server` class attributes including the session states
has moved to the `runtime` submodule, and the `Server` class has a `_runtime` attribute.

Ref: https://github.com/streamlit/streamlit/pull/5136
"""

VER_GTE_1_14_0 = ST_VERSION >= version.parse("1.14.0")
""" Since 1.14.0, Runtime is a singleton.
So we can access it via `Runtime.instance()` directly without the server object,
and use it as a global object to attach some our original attributes
instead of the server object.

Ref: https://github.com/streamlit/streamlit/pull/5432
"""

VER_GTE_1_18_0 = ST_VERSION >= version.parse("1.18.0")
""" Since 1.18.0, Streamlit introduced `SessionManager` protocol
to abstract and improve the session behavior.

Ref: https://github.com/streamlit/streamlit/pull/5856
"""

__all__ = [
    "VER_GTE_1_12_0",
    "VER_GTE_1_12_1",
    "VER_GTE_1_14_0",
    "VER_GTE_1_18_0",
]
