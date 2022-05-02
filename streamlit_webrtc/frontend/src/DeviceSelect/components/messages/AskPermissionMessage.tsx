import React from "react";
import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

const AskPermissionMessage: React.VFC = () => {
  return (
    <Message>
      {useTranslation("device_ask_permission") ||
        "Please allow the app to use your media devices"}
    </Message>
  );
};

export default AskPermissionMessage;
