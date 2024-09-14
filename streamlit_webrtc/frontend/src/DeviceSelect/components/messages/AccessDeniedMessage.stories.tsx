import type { Meta, StoryObj } from "@storybook/react";

import AccessDeniedMessage from "./AccessDeniedMessage";

const meta: Meta<typeof AccessDeniedMessage> = {
  title: "DeviceSelect/AccessDeniedMessage",
  component: AccessDeniedMessage,
};

export default meta;
type Story = StoryObj<typeof AccessDeniedMessage>;

export const Default: Story = {
  args: {
    error: new Error("This is an error"),
  },
};
