import type { Meta, StoryObj } from "@storybook/react";

import MediaApiNotAvailableMessage from "./MediaApiNotAvailableMessage";

const meta: Meta<typeof MediaApiNotAvailableMessage> = {
  title: "DeviceSelect/MediaApiNotAvailableMessage",
  component: MediaApiNotAvailableMessage,
};

export default meta;
type Story = StoryObj<typeof MediaApiNotAvailableMessage>;

export const Default: Story = {
  args: {},
};
