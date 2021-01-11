import React, { useEffect } from "react";

interface VisibilitySwitchProps extends React.ComponentProps<"div"> {
  visible?: boolean;
  onVisibilityChange: (newVisibility: boolean) => void;
}
const VisibilitySwitch = ({
  visible = true,
  onVisibilityChange,
  ...divProps
}: VisibilitySwitchProps) => {
  useEffect(() => {
    onVisibilityChange(visible);
  }, [visible, onVisibilityChange]);

  return (
    <div
      style={{
        ...divProps.style,
        display: visible ? divProps.style?.display : "none",
      }}
      {...divProps}
    />
  );
};

export default React.memo(VisibilitySwitch);
