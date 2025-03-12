import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

export interface AccessDeniedMessageProps {
  error: Error;
}
function AccessDeniedMessage(props: AccessDeniedMessageProps) {
  return (
    <Message>
      {useTranslation("device_access_denied") || "Access denied"} (
      {props.error.message})
    </Message>
  );
}

export default AccessDeniedMessage;
