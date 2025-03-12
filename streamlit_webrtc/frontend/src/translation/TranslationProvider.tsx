import React, { useMemo } from "react";
import { useRenderData } from "streamlit-component-lib-react-hooks";
import { Translations } from "./types";
import { translationContext } from "./context";
interface TranslationProviderProps {
  children: React.ReactNode;
}
function TranslationProvider(props: TranslationProviderProps) {
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
}

export default React.memo(TranslationProvider);
