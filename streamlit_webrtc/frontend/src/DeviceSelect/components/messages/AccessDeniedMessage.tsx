import React from "react";
import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

interface AccessDeniedMessageProps {
  error: Error;
}
const AccessDeniedMessage: React.VFC<AccessDeniedMessageProps> = (props) => {
  return (
    <Message>
      {useTranslation("device_access_denied") || "Access denied"} (
      {props.error.message})
    </Message>
  );
};

export default AccessDeniedMessage;
