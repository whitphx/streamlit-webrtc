import Message from "./Message";
import { useTranslation } from "../../../translation/useTranslation";

function AskPermissionMessage() {
  return (
    <Message>
      {useTranslation("device_ask_permission") ||
        "Please allow the app to use your media devices"}
    </Message>
  );
}

export default AskPermissionMessage;
