import type { Meta, StoryObj } from "@storybook/react";

import DeviceSelect from "./DeviceSelect";

const meta: Meta<typeof DeviceSelect> = {
  title: "DeviceSelect/DeviceSelect",
  component: DeviceSelect,
  argTypes: {
    onSelect: { action: "selected" },
  },
};

export default meta;
type Story = StoryObj<typeof DeviceSelect>;

export const Both: Story = {
  args: {
    video: true,
    audio: true,
  },
};

export const VideoOnly: Story = {
  args: {
    video: true,
    audio: false,
  },
};

export const AudioOnly: Story = {
  args: {
    video: false,
    audio: true,
  },
};
