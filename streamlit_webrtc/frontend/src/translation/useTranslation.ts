import React, { useContext } from "react";
import { Translations } from "./types";

export const translationContext = React.createContext<Translations | undefined>(
  undefined,
);

export const useTranslation = (key: keyof Translations) => {
  const contextValue = useContext(translationContext);
  if (contextValue == null) {
    return null;
  }

  return contextValue[key];
};
