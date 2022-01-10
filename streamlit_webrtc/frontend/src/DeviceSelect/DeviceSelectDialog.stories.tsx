import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceSelectDialog from "./DeviceSelectDialog";

export default {
  title: "DeviceSelect/DeviceSelectDialog",
  component: DeviceSelectDialog,
  argTypes: {
    onClose: { action: "closed" },
    onSelect: { action: "selected" },
  },
} as ComponentMeta<typeof DeviceSelectDialog>;

const Template: ComponentStory<typeof DeviceSelectDialog> = (args) => (
  <DeviceSelectDialog {...args} />
);

export const Default = Template.bind({});
Default.args = {
  video: true,
  audio: true,
  open: false,
};
