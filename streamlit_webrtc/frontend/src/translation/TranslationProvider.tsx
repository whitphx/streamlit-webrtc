import React, { useMemo, useContext } from "react";
import { useRenderData } from "streamlit-component-lib-react-hooks";
import { Translations } from "./types";

const translationContext = React.createContext<Translations | undefined>(
  undefined,
);

export const useTranslation = (key: keyof Translations) => {
  const contextValue = useContext(translationContext);
  if (contextValue == null) {
    return null;
  }

  return contextValue[key];
};

interface TranslationProviderProps {
  children: React.ReactNode;
}
const TranslationProvider: React.VFC<TranslationProviderProps> = (props) => {
  const renderData = useRenderData();
  const {
    start,
    stop,
    select_device,
    device_ask_permission,
    device_not_available,
    device_access_denied,
    media_api_not_available,
  } = renderData.args["translations"] || {};
  const value: Translations = useMemo(
    () => ({
      start,
      stop,
      select_device,
      device_ask_permission,
      device_not_available,
      device_access_denied,
      media_api_not_available,
    }),
    [
      start,
      stop,
      select_device,
      device_ask_permission,
      device_not_available,
      device_access_denied,
      media_api_not_available,
    ],
  );
  return (
    <translationContext.Provider value={value}>
      {props.children}
    </translationContext.Provider>
  );
};

export default React.memo(TranslationProvider);
