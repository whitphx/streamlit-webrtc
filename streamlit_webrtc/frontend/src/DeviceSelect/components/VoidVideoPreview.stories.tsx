import React from "react";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import VoidVideoPreview from "./VoidVideoPreview";

export default {
  title: "DeviceSelect/VoidVideoPreview",
  component: VoidVideoPreview,
} as ComponentMeta<typeof VoidVideoPreview>;

export const Default: ComponentStory<typeof VoidVideoPreview> = () => (
  <VoidVideoPreview />
);
