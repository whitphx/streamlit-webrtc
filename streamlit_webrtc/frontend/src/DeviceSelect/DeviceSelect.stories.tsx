import type { Story } from "@ladle/react";

import DeviceSelect, { DeviceSelectProps } from "./DeviceSelect";

const Base: Story<DeviceSelectProps> = (props: DeviceSelectProps) => (
  <DeviceSelect {...props} />
);
Base.argTypes = {
  onSelectionResolved: { action: "selection resolved" },
  onVideoSelect: { action: "video selected" },
  onAudioSelect: { action: "audio selected" },
};

export const Both = Base.bind({});
Both.args = {
  video: true,
  audio: true,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelectionResolved: () => {},
  onVideoSelect: () => {},
  onAudioSelect: () => {},
};

export const VideoOnly = Base.bind({});
VideoOnly.args = {
  video: true,
  audio: false,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelectionResolved: () => {},
  onVideoSelect: () => {},
  onAudioSelect: () => {},
};

export const AudioOnly = Base.bind({});
AudioOnly.args = {
  video: false,
  audio: true,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelectionResolved: () => {},
  onVideoSelect: () => {},
  onAudioSelect: () => {},
};
