import type { Meta, StoryObj } from "@storybook/react";

import Message from "./Message";

const meta: Meta<typeof Message> = {
  title: "DeviceSelect/Message",
  component: Message,
};

export default meta;
type Story = StoryObj<typeof Message>;

export const Default: Story = {
  args: {
    children: "Lorem ipsum",
  },
};
