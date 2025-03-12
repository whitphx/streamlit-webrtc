import type { Story } from "@ladle/react";

import Message from "./Message";

export const Default: Story = () => <Message>Lorem ipsum</Message>;
Default.args = {
  children: "Lorem ipsum",
};
