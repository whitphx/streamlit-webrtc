### Fixed

- Reset stale SDP answer state left in an idle WebRTC context so a stopped
  session can start again without requiring an extra cancellation.
