import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import AskPermissionMessage from "./AskPermissionMessage";

export default {
  title: "DeviceSelect/AskPermissionMessage",
  component: AskPermissionMessage,
} as ComponentMeta<typeof AskPermissionMessage>;

const Template: ComponentStory<typeof AskPermissionMessage> = (args) => (
  <AskPermissionMessage {...args} />
);

export const Default = Template.bind({});
Default.args = {};
