import { useContext } from "react";
import { Translations } from "./types";
import { translationContext } from "./context";

export const useTranslation = (key: keyof Translations) => {
  const contextValue = useContext(translationContext);
  if (contextValue == null) {
    return null;
  }

  return contextValue[key];
};
