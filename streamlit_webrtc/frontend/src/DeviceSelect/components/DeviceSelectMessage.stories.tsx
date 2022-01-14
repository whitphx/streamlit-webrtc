import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceSelectMessage from "./DeviceSelectMessage";

export default {
  title: "DeviceSelect/DeviceSelectMessage",
  component: DeviceSelectMessage,
} as ComponentMeta<typeof DeviceSelectMessage>;

const Template: ComponentStory<typeof DeviceSelectMessage> = (args) => (
  <DeviceSelectMessage {...args} />
);

export const Default = Template.bind({});
Default.args = {
  children: "Lorem ipsum",
};
