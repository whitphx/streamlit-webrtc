import type { Meta, StoryObj } from "@storybook/react";

import VoidVideoPreview from "./VoidVideoPreview";

const meta: Meta<typeof VoidVideoPreview> = {
  title: "DeviceSelect/VoidVideoPreview",
  component: VoidVideoPreview,
};

export default meta;
type Story = StoryObj<typeof VoidVideoPreview>;

export const Default: Story = {};
