import type { Story } from "@ladle/react";

import AccessDeniedMessage, { AccessDeniedMessageProps } from "./AccessDeniedMessage";

export const Default: Story<AccessDeniedMessageProps> = (props: AccessDeniedMessageProps) => <AccessDeniedMessage {...props} />
Default.args = {
  error: new Error("This is an error"),
};
