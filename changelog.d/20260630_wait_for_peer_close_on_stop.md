### Fixed

- Wait for the peer connection close coroutine when stopping a `WebRtcWorker`,
  so subsequent starts with the same key do not race against asynchronous peer
  connection teardown.
