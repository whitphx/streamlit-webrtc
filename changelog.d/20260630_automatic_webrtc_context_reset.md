### Fixed

- Reset `webrtc_streamer()` backend state when its frontend session ends, so
  stale worker, signalling, and component snapshot state are not reused on the
  next start with the same key.
