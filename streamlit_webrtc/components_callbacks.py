"""Patch to use callbacks with Streamlit custom components.

Usage
-----

>>> import streamlit.components.v1 as components
>>> from components_callbacks import register_callback
>>>
>>> print("Script begins...")
>>>
>>> def my_callback(arg1, arg2):
>>>     print("New component value:", st.session_state.my_key)
>>>     print("Args:", arg1, arg2)
>>>
>>> register_callback("my_key", my_callback, "hello", arg2="world")
>>>
>>> my_component = components.declare_component(...)
>>> my_component(..., key="my_key")


Here's the result when you call Streamlit.setComponentValue():

    New component value: <value set through Streamlit.setComponentValue()>
    Args: hello world
    Script begins...

"""
from streamlit import session_state as _state
from streamlit.components.v1 import components as _components


def _patch_register_widget(register_widget):
    def wrapper_register_widget(*args, **kwargs):
        user_key = kwargs.get("user_key", None)
        callbacks = _state.get("_components_callbacks", None)

        # Check if a callback was registered for that user_key.
        if user_key and callbacks and user_key in callbacks:
            callback = callbacks[user_key]

            # Add callback-specific args for the real register_widget function.
            kwargs["on_change_handler"] = callback[0]
            kwargs["args"] = callback[1]
            kwargs["kwargs"] = callback[2]

        # Call the original function with updated kwargs.
        return register_widget(*args, **kwargs)

    return wrapper_register_widget


# Patch function only once.
if not hasattr(_components.register_widget, "__callbacks_patched__"):
    setattr(_components.register_widget, "__callbacks_patched__", True)
    _components.register_widget = _patch_register_widget(_components.register_widget)


def register_callback(element_key, callback, *callback_args, **callback_kwargs):
    # Initialize callbacks store.
    if "_components_callbacks" not in _state:
        _state._components_callbacks = {}

    # Register a callback for a given element_key.
    _state._components_callbacks[element_key] = (
        callback,
        callback_args,
        callback_kwargs,
    )
