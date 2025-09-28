# Tutorial

Learn how to build real-time video processing apps with Streamlit-WebRTC step by step.

## Basic Usage

Create `app.py` with the content below:

```python
--8<-- "./examples/tutorial/01_basic_usage.py"
```

Unlike other Streamlit components, `webrtc_streamer()` requires the `key` argument as a unique identifier. Set an arbitrary string to it.

Then run it with Streamlit and open http://localhost:8501/:

```bash
streamlit run app.py
```

You see the app view, so click the "START" button.

Then, video and audio streaming starts. If asked for permissions to access the camera and microphone, allow it.

![Basic example of streamlit-webrtc](./images/streamlit_webrtc_basic.gif)

## Adding Video Processing

Next, edit `app.py` as below and run it again:

```python
--8<-- "./examples/tutorial/02_video_processing.py"
```

Now the video is vertically flipped.

![Vertically flipping example](./images/streamlit_webrtc_flipped.gif)

As shown in this example, you can edit the video frames by defining a callback that receives and returns a frame and passing it to the `video_frame_callback` argument (or `audio_frame_callback` for audio manipulation).

The input and output frames are instances of [`av.VideoFrame`](https://pyav.org/docs/develop/api/video.html#av.video.frame.VideoFrame) (or [`av.AudioFrame`](https://pyav.org/docs/develop/api/audio.html#av.audio.frame.AudioFrame) when dealing with audio) from the [`PyAV` library](https://pyav.org/).

You can inject any kinds of image (or audio) processing inside the callback.

## Pass Parameters to the Callback

You can also pass parameters to the callback.

In the example below, a boolean `flip` flag is used to turn on/off the image flipping:

```python
--8<-- "./examples/tutorial/03_parameters.py"
```

## Pull Values from the Callback

Sometimes we want to read the values generated in the callback from the outer scope.

Note that the callback is executed in a forked thread running independently of the main script, so we have to take care of the following points and need some tricks for implementation like the example below:

* **Thread-safety** - Passing the values between inside and outside the callback must be thread-safe.
* **Using a loop to poll the values** - During media streaming, while the callback continues to be called, the main script execution stops at the bottom as usual. So we need to use a loop to keep the main script running and get the values from the callback in the outer scope.

The following example passes the image frames from the callback to the outer scope and continuously processes them in a loop. In this example, simple image analysis (calculating the histogram) is done on the image frames:

```python
--8<-- "./examples/tutorial/04_pull_values.py"
```

[`threading.Lock`](https://docs.python.org/3/library/threading.html#lock-objects) is one standard way to control variable accesses across threads. A dict object `img_container` here is a mutable container shared by the callback and the outer scope and the `lock` object is used at assigning and reading the values to/from the container for thread-safety.

## Callback Limitations

The callbacks are executed in forked threads different from the main one, so there are some limitations:

* Streamlit methods (`st.*` such as `st.write()`) do not work inside the callbacks.
* Variables inside the callbacks cannot be directly referred to from the outside.
* The `global` keyword does not work expectedly in the callbacks.
* You have to care about thread-safety when accessing the same objects both from outside and inside the callbacks as stated in the section above.

## Ready for Production?

When you're ready to deploy your app, see the [Deployment Guide](deployment.md) for:

- HTTPS configuration requirements
- STUN/TURN server setup
- Platform-specific deployment instructions
- Troubleshooting common issues
