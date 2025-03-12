import React from "react";
import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

export interface DeviceNotAvailableMessageProps {
  error: Error;
}
const DeviceNotAvailableMessage: React.VFC<DeviceNotAvailableMessageProps> = (
  props,
) => {
  return (
    <Message>
      {useTranslation("device_not_available") || "Device not available"} (
      {props.error.message})
    </Message>
  );
};

export default DeviceNotAvailableMessage;
