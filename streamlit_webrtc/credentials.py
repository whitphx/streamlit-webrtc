"""
MIT License

Copyright (c) 2024 Freddy Boulton

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
# Original: https://github.com/freddyaboulton/fastrtc/blob/66f0a81b76684c5d58761464fb67642891066f93/LICENSE

import os
from typing import Literal, Optional

import requests


def get_hf_turn_credentials(token: Optional[str] = None):
    if token is None:
        token = os.getenv("HF_TOKEN")
    credentials = requests.get(
        "https://fastrtc-turn-server-login.hf.space/credentials",
        headers={"X-HF-Access-Token": token},
    )
    if not credentials.status_code == 200:
        raise ValueError("Failed to get credentials from HF turn server")
    return {
        "iceServers": [
            {
                "urls": "turn:gradio-turn.com:80",
                **credentials.json(),
            },
        ]
    }


def get_twilio_turn_credentials(
    twilio_sid: Optional[str] = None, twilio_token: Optional[str] = None
):
    try:
        from twilio.rest import Client
    except ImportError:
        raise ImportError("Please install twilio with `pip install twilio`")

    if not twilio_sid and not twilio_token:
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")

    client = Client(twilio_sid, twilio_token)

    token = client.tokens.create()

    return {
        "iceServers": token.ice_servers,
        "iceTransportPolicy": "relay",
    }


def get_turn_credentials(method: Literal["hf", "twilio"] = "hf", **kwargs):
    if method == "hf":
        return get_hf_turn_credentials(**kwargs)
    elif method == "twilio":
        return get_twilio_turn_credentials(**kwargs)
    else:
        raise ValueError("Invalid method. Must be 'hf' or 'twilio'")
