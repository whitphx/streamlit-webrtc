import React from "react";
import Paper from "@mui/material/Paper";
import { ComponentStory, ComponentMeta } from "@storybook/react";

import Defer from "./Defer";

export default {
  title: "DeviceSelect/Defer",
  component: Defer,
} as ComponentMeta<typeof Defer>;

const InnerComponent = () => <Paper>Lorem ipsum</Paper>;

export const Default: ComponentStory<typeof Defer> = () => (
  <Defer time={1000}>
    <InnerComponent />
  </Defer>
);
