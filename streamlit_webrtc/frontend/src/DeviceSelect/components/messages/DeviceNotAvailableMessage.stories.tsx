import type { Meta, StoryObj } from "@storybook/react";

import DeviceNotAvailableMessage from "./DeviceNotAvailableMessage";

const meta: Meta<typeof DeviceNotAvailableMessage> = {
  title: "DeviceSelect/DeviceNotAvailableMessage",
  component: DeviceNotAvailableMessage,
};

export default meta;
type Story = StoryObj<typeof DeviceNotAvailableMessage>;

export const Default: Story = {
  args: {
    error: new Error("This is an error"),
  },
};
