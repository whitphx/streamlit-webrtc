import type { Meta, StoryObj } from "@storybook/react";

import AskPermissionMessage from "./AskPermissionMessage";

const meta: Meta<typeof AskPermissionMessage> = {
  title: "DeviceSelect/AskPermissionMessage",
  component: AskPermissionMessage,
};

export default meta;
type Story = StoryObj<typeof AskPermissionMessage>;

export const Default: Story = {
  args: {},
};
