import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceSelectError from "./DeviceSelectError";

export default {
  title: "DeviceSelect/DeviceSelectError",
  component: DeviceSelectError,
} as ComponentMeta<typeof DeviceSelectError>;

const Template: ComponentStory<typeof DeviceSelectError> = (args) => (
  <DeviceSelectError {...args} />
);

export const Default = Template.bind({});
Default.args = {
  children: "Lorem ipsum",
};
