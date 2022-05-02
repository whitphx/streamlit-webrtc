import React from "react";
import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

const MediaApiNotAvailableMessage: React.VFC = () => {
  return (
    <Message>
      {useTranslation("media_api_not_available") || "Media API not available"}
    </Message>
  );
};

export default MediaApiNotAvailableMessage;
