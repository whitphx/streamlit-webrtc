import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import AccessDeniedMessage from "./AccessDeniedMessage";

export default {
  title: "DeviceSelect/AccessDeniedMessage",
  component: AccessDeniedMessage,
} as ComponentMeta<typeof AccessDeniedMessage>;

const Template: ComponentStory<typeof AccessDeniedMessage> = (args) => (
  <AccessDeniedMessage {...args} />
);

export const Default = Template.bind({});
Default.args = {
  error: new Error("This is an error"),
};
