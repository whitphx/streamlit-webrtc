import Message from "./Message";
import { useTranslation } from "../../../translation/useTranslation";

export interface DeviceNotAvailableMessageProps {
  error: Error;
}
function DeviceNotAvailableMessage(props: DeviceNotAvailableMessageProps) {
  return (
    <Message>
      {useTranslation("device_not_available") || "Device not available"} (
      {props.error.message})
    </Message>
  );
}

export default DeviceNotAvailableMessage;
