import Paper from "@mui/material/Paper";
import type { Meta, StoryObj } from "@storybook/react";

import Defer from "./Defer";

const meta: Meta<typeof Defer> = {
  title: "DeviceSelect/Defer",
  component: Defer,
};

export default meta;
type Story = StoryObj<typeof Defer>;

const InnerComponent = () => <Paper>Lorem ipsum</Paper>;

export const Default: Story = {
  args: {
    time: 1000,
    children: <InnerComponent />,
  },
};
