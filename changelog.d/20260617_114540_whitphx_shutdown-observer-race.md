### Fixed

- Fixed a race in shutdown observer cleanup that could raise `AttributeError: 'NoneType' object has no attribute 'is_alive'` when a WebRTC worker stops from overlapping shutdown paths.
