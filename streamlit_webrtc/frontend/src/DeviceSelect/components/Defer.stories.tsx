import Paper from "@mui/material/Paper";
import type { Story } from "@ladle/react";

import Defer, { DeferProps } from "./Defer";

const InnerComponent = () => <Paper>Lorem ipsum</Paper>;

export const Default: Story<DeferProps> = (props: DeferProps) => <Defer {...props} />
Default.args = {
  time: 1000,
  children: <InnerComponent />,
};
