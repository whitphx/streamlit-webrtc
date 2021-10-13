# streamlit-webrtc
**Handling and transmitting real-time video/audio streams over the network with Streamlit**

[![Tests](https://github.com/whitphx/streamlit-webrtc/workflows/Tests/badge.svg?branch=main)](https://github.com/whitphx/streamlit-webrtc/actions?query=workflow%3ATests+branch%3Amain)
[![Frontend Tests](https://github.com/whitphx/streamlit-webrtc/workflows/Frontend%20tests/badge.svg?branch=main)](https://github.com/whitphx/streamlit-webrtc/actions?query=workflow%3A%22Frontend+tests%22+branch%3Amain)

[![PyPI](https://img.shields.io/pypi/v/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - License](https://img.shields.io/pypi/l/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)

[![GitHub Sponsors](https://img.shields.io/github/sponsors/whitphx?label=Sponsor%20me%20on%20GitHub%20Sponsors&style=social)](https://github.com/sponsors/whitphx)

<a href="https://www.buymeacoffee.com/whitphx" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" width="180" height="50" ></a>

![Demo movie](https://aws1.discourse-cdn.com/business7/uploads/streamlit/original/2X/a/af111a7393c77cb69d7712ac8e71ca862feaeb24.gif)

## Install
```shell
$ pip install -U streamlit-webrtc
```

## Quick tutorial
Create `app.py` with the content below.
```py
from streamlit_webrtc import webrtc_streamer

webrtc_streamer(key="sample")
```
Unlike other Streamlit components, `webrtc_streamer()` requires the `key` argument.

Then run it with Streamlit and open http://localhost:8501/.
```shell
$ streamlit run app.py
```

You see this screen, so click the "START" button.
![The default initial view](./docs/images/default_init_view.png)

Then, video and audio streaming starts. If asked for permissions to access the camera and microphone, allow it.
![Basic example of streamlit-webrtc](./docs/images/streamlit_webrtc_basic.gif)

Next, edit `app.py` as below and run it again.
```py
from streamlit_webrtc import webrtc_streamer
import av


class VideoProcessor:
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")

        flipped = img[::-1,:,:]

        return av.VideoFrame.from_ndarray(flipped, format="bgr24")


webrtc_streamer(key="example", video_processor_factory=VideoProcessor)
```

Now the video is vertically flipped.
![Vertically flipping example](./docs/images/streamlit_webrtc_flipped.gif)

As an example above, you can edit the video frames by defining a callback method `recv(frame)` and a class including it and passing the class to the `video_processor_factory` argument.
This callback receives and returns a frame. The frame is an instance of [`av.VideoFrame`](https://pyav.org/docs/develop/api/video.html#av.video.frame.VideoFrame) (or [`av.AudioFrame`](https://pyav.org/docs/develop/api/audio.html#av.audio.frame.AudioFrame) when dealing with audio) of [`PyAV` library](https://pyav.org/).

You can inject any kinds of image (or audio) processing inside the callback.
See examples below for more applications.

Note that there are some limitations in this callback. See the section below.

## Example [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/whitphx/streamlit-webrtc-example/main/app.py)

TODO

You can try out the sample app using the following commands.
```
$ pip install streamlit-webrtc opencv-python-headless matplotlib pydub
$ streamlit run https://raw.githubusercontent.com/whitphx/streamlit-webrtc-example/main/app.py
```

You can also try it out on [Streamlit Sharing](https://share.streamlit.io/whitphx/streamlit-webrtc-example/main/app.py).

The deployment of this sample app is managed in this repository: https://github.com/whitphx/streamlit-webrtc-example/.

## Limitations
TODO

## API
Currently there is no documentation about the interface. See the example [app.py](./app.py) for the usage.
The API is not finalized yet and can be changed without backward compatiblity in the future releases until v1.0.

### For users since versions `<0.20`
`VideoTransformerBase` and its `transform` method have been marked as deprecated in v0.20.0. Please use `VideoProcessorBase#recv()` instead.
Note that the signature of the `recv` method is different from the `transform` in that the `recv` has to return an instance of `av.VideoFrame` or `av.AudioFrame`. See the samples in [app.py](./app.py).

## Resources
* [Building a Web-Based Real-Time Computer Vision App with Streamlit (dev.to)](https://dev.to/whitphx/build-a-web-based-real-time-computer-vision-app-with-streamlit-57l2)
  * This post explains how to use `streamlit-webrtc` to build a real-time computer vision app.
* [New Component: streamlit-webrtc, a new way to deal with real-time media streams (Streamlit Community)](https://discuss.streamlit.io/t/new-component-streamlit-webrtc-a-new-way-to-deal-with-real-time-media-streams/8669)
  * This is a forum topic where `streamlit-webrtc` has been introduced and discussed about.
