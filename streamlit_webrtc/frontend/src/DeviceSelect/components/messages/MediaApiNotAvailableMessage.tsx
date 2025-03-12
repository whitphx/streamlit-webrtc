import Message from "./Message";
import { useTranslation } from "../../../translation/TranslationProvider";

function MediaApiNotAvailableMessage() {
  return (
    <Message>
      {useTranslation("media_api_not_available") || "Media API not available"}
    </Message>
  );
};

export default MediaApiNotAvailableMessage;
