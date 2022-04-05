import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import MediaApiNotAvailableMessage from "./MediaApiNotAvailableMessage";

export default {
  title: "DeviceSelect/MediaApiNotAvailableMessage",
  component: MediaApiNotAvailableMessage,
} as ComponentMeta<typeof MediaApiNotAvailableMessage>;

const Template: ComponentStory<typeof MediaApiNotAvailableMessage> = (args) => (
  <MediaApiNotAvailableMessage {...args} />
);

export const Default = Template.bind({});
Default.args = {};
