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
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

from ._compat import cache_data
from .config import RTCIceServer

LOGGER = logging.getLogger(__name__)


HF_ICE_SERVER_TTL = 3600  # 1 hour. Not sure if this is the best value.


@cache_data(ttl=HF_ICE_SERVER_TTL)
def get_hf_ice_servers(token: str) -> List[RTCIceServer]:
    if not token:
        raise ValueError("Hugging Face API token is not set")

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


CLOUDFLARE_CRED_TTL = 3600  # 1 hour. Cloudflare allows up to 48 hours. Shorter TTL should be ok for this library's use case.


@cache_data(ttl=CLOUDFLARE_CRED_TTL)
def get_cloudflare_ice_servers(
    turn_key_id: str, turn_key_api_token: str
) -> List[RTCIceServer]:
    if not turn_key_id or not turn_key_api_token:
        raise ValueError("Cloudflare TURN key ID or API token is not set")

    req = urllib.request.Request(
        "https://rtc.live.cloudflare.com/v1/turn/keys/"
        f"{urllib.parse.quote(turn_key_id, safe='')}/credentials/generate-ice-servers",
        data=json.dumps({"ttl": CLOUDFLARE_CRED_TTL}).encode(),
        headers={
            "Authorization": f"Bearer {turn_key_api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        # This runs on the Streamlit script thread, so a hung connection would
        # stall the whole rerun without a timeout.
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status not in (200, 201):
                raise ValueError(
                    "Failed to get credentials from Cloudflare Realtime TURN"
                )
            return json.loads(response.read())["iceServers"]
    except urllib.error.URLError:
        raise ValueError("Failed to get credentials from Cloudflare Realtime TURN")


TWILIO_CRED_TTL = 3600  # 1 hour. Twilio's default is 1 day. Shorter TTL should be ok for this library's use case.


@cache_data(ttl=TWILIO_CRED_TTL)
def get_twilio_ice_servers(twilio_sid: str, twilio_token: str) -> List[RTCIceServer]:
    try:
        from twilio.rest import Client
    except ImportError:
        raise ImportError(
            "Twilio library is not installed. Please install it with `pip install twilio`"
        )

    client = Client(twilio_sid, twilio_token)

    token = client.tokens.create(ttl=TWILIO_CRED_TTL)

    return token.ice_servers


def _get_credential_pair(
    first_env_var: str, second_env_var: str, provider: str
) -> Optional[Tuple[str, str]]:
    first = os.getenv(first_env_var)
    second = os.getenv(second_env_var)
    if first and second:
        return first, second
    # Half-configured is almost always a typo or a forgotten secret rather than
    # a deliberate opt-out, so say so instead of silently skipping the provider.
    if first or second:
        set_var, unset_var = (
            (first_env_var, second_env_var)
            if first
            else (second_env_var, first_env_var)
        )
        LOGGER.warning(
            "%s is set but %s is not. %s's STUN/TURN servers will not be used.",
            set_var,
            unset_var,
            provider,
        )
    return None


@cache_data(ttl=min(HF_ICE_SERVER_TTL, TWILIO_CRED_TTL, CLOUDFLARE_CRED_TTL))
def get_available_ice_servers() -> List[RTCIceServer]:
    cloudflare_creds = _get_credential_pair(
        "CLOUDFLARE_TURN_KEY_ID", "CLOUDFLARE_TURN_KEY_API_TOKEN", "Cloudflare"
    )
    if cloudflare_creds:
        LOGGER.info(
            "Cloudflare credentials found, using Cloudflare's STUN/TURN servers."
        )
        try:
            return get_cloudflare_ice_servers(*cloudflare_creds)
        except Exception as e:
            LOGGER.warning("Failed to get TURN credentials from Cloudflare: %s", e)

    twilio_creds = _get_credential_pair(
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "Twilio"
    )
    if twilio_creds:
        LOGGER.info("Twilio credentials found, using Twilio's STUN/TURN servers.")
        try:
            return get_twilio_ice_servers(*twilio_creds)
        except Exception as e:
            LOGGER.warning("Failed to get TURN credentials from Twilio: %s", e)

    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        LOGGER.info("Hugging Face token found, using Hugging Face's STUN/TURN servers.")
        try:
            hf_turn_servers = get_hf_ice_servers(hf_token)
            LOGGER.info("Successfully got TURN credentials from Hugging Face.")
            LOGGER.info(
                "Using TURN server from Hugging Face and STUN server from Google."
            )
            ice_servers = hf_turn_servers + [
                RTCIceServer(urls="stun:stun.l.google.com:19302"),
            ]
            return ice_servers
        except Exception as e:
            LOGGER.warning("Failed to get TURN credentials from Hugging Face: %s", e)

    # NOTE: aiortc anyway uses this STUN server by default if the ICE server config is not set.
    # Ref: https://github.com/aiortc/aiortc/blob/3ff9bdd03f22bf511a8d304df30f29392338a070/src/aiortc/rtcicetransport.py#L204-L209
    # We set the STUN server here as this will be used on the browser side as well.
    LOGGER.info("Use STUN server from Google.")
    return [RTCIceServer(urls="stun:stun.l.google.com:19302")]
