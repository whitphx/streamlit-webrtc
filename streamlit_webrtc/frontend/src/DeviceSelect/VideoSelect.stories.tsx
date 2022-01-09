import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import VideoSelect from "./VideoSelect";

export default {
  title: "DeviceSelect/VideoSelect",
  component: VideoSelect,
} as ComponentMeta<typeof VideoSelect>;

export const Default: ComponentStory<typeof VideoSelect> = () => (
  <VideoSelect />
);
