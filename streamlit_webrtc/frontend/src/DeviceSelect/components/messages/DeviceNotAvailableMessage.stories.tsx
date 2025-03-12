import type { Story } from "@ladle/react";

import DeviceNotAvailableMessage, { DeviceNotAvailableMessageProps } from "./DeviceNotAvailableMessage";

export const Default: Story<DeviceNotAvailableMessageProps> = (props: DeviceNotAvailableMessageProps) => <DeviceNotAvailableMessage {...props} />
Default.args = {
  error: new Error("This is an error"),
};
