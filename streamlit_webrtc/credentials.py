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

import json
import logging
import os
import urllib.error
import urllib.request
from typing import List, Optional

from .config import RTCIceServer

LOGGER = logging.getLogger(__name__)


def get_hf_ice_servers(token: Optional[str] = None) -> List[RTCIceServer]:
    if token is None:
        token = os.getenv("HF_TOKEN")

    if token is None:
        raise ValueError("HF_TOKEN is not set")

    req = urllib.request.Request(
        "https://fastrtc-turn-server-login.hf.space/credentials",
        headers={"X-HF-Access-Token": token},
    )
    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                raise ValueError("Failed to get credentials from HF turn server")
            credentials = json.loads(response.read())
            return [
                {
                    "urls": "turn:gradio-turn.com:80",
                    **credentials,
                },
            ]
    except urllib.error.URLError:
        raise ValueError("Failed to get credentials from HF turn server")


def get_twilio_ice_servers(
    twilio_sid: Optional[str] = None, twilio_token: Optional[str] = None
) -> List[RTCIceServer]:
    try:
        from twilio.rest import Client
    except ImportError:
        raise ImportError("Please install twilio with `pip install twilio`")

    if not twilio_sid and not twilio_token:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")

    if twilio_sid is None or twilio_token is None:
        raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")

    client = Client(twilio_sid, twilio_token)

    token = client.tokens.create()

    return token.ice_servers


def get_available_ice_servers() -> List[RTCIceServer]:
    try:
        LOGGER.info("Try to use TURN server from Hugging Face.")
        ice_servers = get_hf_ice_servers()
        LOGGER.info("Successfully got TURN credentials from Hugging Face.")
        return ice_servers
    except Exception as e:
        LOGGER.info("Failed to get TURN credentials from Hugging Face: %s", e)

    try:
        LOGGER.info("Try to use TURN server from Twilio.")
        ice_servers = get_twilio_ice_servers()
        LOGGER.info("Successfully got TURN credentials from Twilio.")
        return ice_servers
    except Exception as e:
        LOGGER.info("Failed to get TURN credentials from Twilio: %s", e)

    LOGGER.info("Use STUN server from Google.")
    return [RTCIceServer(urls="stun:stun.l.google.com:19302")]
