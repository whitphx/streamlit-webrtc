# streamlit-webrtc

[![Tests](https://github.com/whitphx/streamlit-webrtc/workflows/Tests/badge.svg?branch=main)](https://github.com/whitphx/streamlit-webrtc/actions?query=workflow%3ATests+branch%3Amain)
[![Frontend Tests](https://github.com/whitphx/streamlit-webrtc/workflows/Frontend%20tests/badge.svg?branch=main)](https://github.com/whitphx/streamlit-webrtc/actions?query=workflow%3A%22Frontend+tests%22+branch%3Amain)

[![PyPI](https://img.shields.io/pypi/v/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - License](https://img.shields.io/pypi/l/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/streamlit-webrtc)](https://pypi.org/project/streamlit-webrtc/)

[![GitHub Sponsors](https://img.shields.io/github/sponsors/whitphx?label=Sponsor%20me%20on%20GitHub%20Sponsors&style=social)](https://github.com/sponsors/whitphx)

<a href="https://www.buymeacoffee.com/whitphx" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" width="180" height="50" ></a>

![Demo movie](https://aws1.discourse-cdn.com/business7/uploads/streamlit/original/2X/a/af111a7393c77cb69d7712ac8e71ca862feaeb24.gif)

## Example [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/whitphx/streamlit-webrtc-example/main/app.py)
You can try out the sample app using the following commands.
```
$ pip install streamlit-webrtc opencv-python
$ streamlit run https://raw.githubusercontent.com/whitphx/streamlit-webrtc-example/main/app.py
```

You can also try it out on [Streamlit Sharing](https://share.streamlit.io/whitphx/streamlit-webrtc-example/main/app.py).

The deployment of this sample app is managed in this repository: https://github.com/whitphx/streamlit-webrtc-example/.

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
