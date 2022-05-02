import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceNotAvailableMessage from "./DeviceNotAvailableMessage";

export default {
  title: "DeviceSelect/DeviceNotAvailableMessage",
  component: DeviceNotAvailableMessage,
} as ComponentMeta<typeof DeviceNotAvailableMessage>;

const Template: ComponentStory<typeof DeviceNotAvailableMessage> = (args) => (
  <DeviceNotAvailableMessage {...args} />
);

export const Default = Template.bind({});
Default.args = {
  error: new Error("This is an error"),
};
