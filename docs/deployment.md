# Deployment Guide

Deploy your Streamlit-WebRTC applications to production environments.

## Overview

When deploying apps to remote servers, there are some important considerations:

- **HTTPS is required** to access local media devices
- **STUN/TURN servers** are required to establish media stream connections
- **Network configuration** may require additional setup

## HTTPS Requirement

`streamlit-webrtc` uses [`getUserMedia()`](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) API to access local media devices, and this method does not work in an insecure context.

A secure context is a page loaded using HTTPS or the `file:///` URL scheme, or a page loaded from localhost.

So, when hosting your app on a remote server, it must be served via HTTPS if your app is using webcam or microphone.

If not, you will encounter an error when starting to use the device. For example, something like this on Chrome:
> Error: navigator.mediaDevices is undefined. It seems the current document is not loaded securely.

### Recommended HTTPS Solutions

**[Streamlit Community Cloud](https://streamlit.io/cloud)** is the recommended way for HTTPS serving. You can easily deploy Streamlit apps with it, and most importantly, it serves the apps via HTTPS automatically by default.

**For development purposes**, sometimes [`suyashkumar/ssl-proxy`](https://github.com/suyashkumar/ssl-proxy) is a convenient tool to serve your app via HTTPS:

```bash
# Assume your app is running on http://localhost:8501
streamlit run your_app.py  

# Then, after downloading the binary from the GitHub page above to ./ssl-proxy
./ssl-proxy -from 0.0.0.0:8000 -to 127.0.0.1:8501  

# Then access https://localhost:8000
```

## STUN Server Configuration

To deploy the app to the cloud, you need to configure the STUN server via the `rtc_configuration` argument:

```python
--8<-- "./examples/tutorial/05_stun_config.py"
```

This configuration is necessary to establish the media streaming connection when the server is on a remote host.

### About STUN Servers

`streamlit-webrtc` uses WebRTC for its video and audio streaming. It has to access a "STUN server" in the global network for remote peers (precisely, peers over NATs) to establish WebRTC connections.

The example above is configured to use `stun.l.google.com:19302`, which is a free STUN server provided by Google.

You can also use any other STUN servers. For example, [one user reported](https://github.com/whitphx/streamlit-webrtc/issues/283#issuecomment-889753789) that Google's STUN server had a huge delay when using from China networks, and the problem was solved by changing the STUN server.

For those familiar with the browser WebRTC API: The value of the `rtc_configuration` argument will be passed to the [`RTCPeerConnection`](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/RTCPeerConnection) constructor on the frontend.

## TURN Server Configuration

⚠️ **You may need to set up a TURN server** in some environments, **including Streamlit Community Cloud**.

Even if the STUN server is properly configured, media streaming may not work in some network environments, either from the server or from the client. For example, if the server is hosted behind a proxy, or if the client is on an office network behind a firewall, the WebRTC packets may be blocked.

In such environments, a [TURN server](https://webrtc.org/getting-started/turn-server) is required.

### TURN Server Options

#### Twilio Network Traversal Service (Recommended)

[Twilio Network Traversal Service](https://www.twilio.com/docs/stun-turn) is a stable and easy-to-use solution. It's a paid service, but you can start with a free trial.

```python
## This sample code is from https://www.twilio.com/docs/stun-turn/api
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

token = client.tokens.create()

# Then, pass the ICE server information to webrtc_streamer().
webrtc_streamer(
    # ...
    rtc_configuration={
        "iceServers": token.ice_servers
    }
    # ...
)
```

The [WebRTC sample app hosted on Community Cloud](https://webrtc.streamlit.app/) uses this option. See [how it retrieves the ICE server information from the Twilio API](https://github.com/whitphx/streamlit-webrtc-example/blob/79ac65994a8c7f91475647d65e63b5040ea35863/sample_utils/turn.py) and [how to use it in the app](https://github.com/whitphx/streamlit-webrtc-example/blob/79ac65994a8c7f91475647d65e63b5040ea35863/pages/1_object_detection.py#L141).

#### Other Options

- **[Open Relay Project](https://www.metered.ca/tools/openrelay/)** provides a free TURN server. However, it does not seem to be stable enough and is often down.
- **Self-hosted TURN server** is also an option. See [this GitHub discussion](https://github.com/whitphx/streamlit-webrtc/issues/335#issuecomment-897326755) for guidance.

## Deployment Platforms

### Streamlit Community Cloud

1. Push your code to GitHub
2. Connect repository to [Streamlit Community Cloud](https://streamlit.io/cloud)
3. Add TURN server credentials to secrets (if needed)
4. Deploy automatically with HTTPS enabled

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "your_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Other Cloud Platforms

When deploying to other platforms (AWS, GCP, Azure, etc.):

1. Ensure HTTPS is configured
2. Configure STUN server in your app
3. Set up TURN server if needed
4. Test WebRTC connectivity from target deployment environment

## Troubleshooting

### Common Issues

**Camera/microphone not accessible:**
- Ensure HTTPS in production (required for WebRTC)
- Check browser permissions
- Verify camera/microphone hardware

**Connection fails:**
- Try with TURN servers for production
- Check firewall settings
- Verify network connectivity

**Performance issues:**
- Reduce video resolution in `media_stream_constraints`
- Optimize frame processing callbacks
- Consider using `async_processing=True`

### Testing Deployment

Before going live, test your deployment:

1. **Local HTTPS testing** - Use ssl-proxy or similar tools
2. **Network testing** - Test from different network environments
3. **Browser testing** - Test across different browsers and devices
4. **Performance testing** - Monitor resource usage and frame rates

## Security Considerations

- **Never expose TURN credentials** in client-side code
- **Use environment variables** for sensitive configuration
- **Implement proper authentication** if needed
- **Consider rate limiting** for resource-intensive operations

## Next Steps

After successful deployment:

1. **Monitor performance** - Track app metrics and user experience
2. **Optimize costs** - Monitor TURN server usage if using paid services
3. **Scale as needed** - Consider load balancing for high-traffic apps
4. **Gather feedback** - Collect user feedback for improvements

For more deployment examples and configurations, see the [sample applications](https://github.com/whitphx/streamlit-webrtc/tree/main/pages) and [examples gallery](https://github.com/whitphx/streamlit-webrtc-example).