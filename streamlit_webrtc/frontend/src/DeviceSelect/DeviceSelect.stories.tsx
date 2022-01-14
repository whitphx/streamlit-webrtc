import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceSelect from "./DeviceSelect";

export default {
  title: "DeviceSelect/DeviceSelect",
  component: DeviceSelect,
  argTypes: {
    onSelect: { action: "selected" },
  },
} as ComponentMeta<typeof DeviceSelect>;

const Template: ComponentStory<typeof DeviceSelect> = (args) => (
  <DeviceSelect {...args} />
);

export const Both = Template.bind({});
Both.args = {
  video: true,
  audio: true,
};

export const VideoOnly = Template.bind({});
VideoOnly.args = {
  video: true,
  audio: false,
};

export const AudioOnly = Template.bind({});
AudioOnly.args = {
  video: false,
  audio: true,
};
