import type { Story } from "@ladle/react";

import InfoHeader, { InfoHeaderProps } from "./InfoHeader";

const Base: Story<InfoHeaderProps> = (props: InfoHeaderProps) => (
  <InfoHeader {...props} />
);

export const ErrorCase = Base.bind({});
ErrorCase.args = {
  error: new Error("Some error"),
  shouldShowTakingTooLongWarning: false,
};

export const TakingTooLongWarningCase = Base.bind({});
TakingTooLongWarningCase.args = {
  error: null,
  shouldShowTakingTooLongWarning: true,
};
