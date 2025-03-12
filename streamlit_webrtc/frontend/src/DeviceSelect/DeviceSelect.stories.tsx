import type { Story } from "@ladle/react";

import DeviceSelect, { DeviceSelectProps } from "./DeviceSelect";

const Base: Story<DeviceSelectProps> = (props: DeviceSelectProps) => <DeviceSelect {...props} />
Base.argTypes = {
  onSelect: { action: "selected" },
}

export const Both = Base.bind({});
Both.args = {
  video: true,
  audio: true,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelect: () => {},
}

export const VideoOnly = Base.bind({});
VideoOnly.args = {
  video: true,
  audio: false,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelect: () => {},
}

export const AudioOnly = Base.bind({});
AudioOnly.args = {
  video: false,
  audio: true,
  defaultVideoDeviceId: undefined,
  defaultAudioDeviceId: undefined,
  onSelect: () => {},
}
