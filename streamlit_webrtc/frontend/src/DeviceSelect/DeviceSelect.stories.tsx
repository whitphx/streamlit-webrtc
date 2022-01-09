import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import DeviceSelect from "./DeviceSelect";

export default {
  title: "DeviceSelect/DeviceSelect",
  component: DeviceSelect,
} as ComponentMeta<typeof DeviceSelect>;

export const Default: ComponentStory<typeof DeviceSelect> = () => (
  <DeviceSelect video audio />
);
