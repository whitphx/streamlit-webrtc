import React from "react";
import { Translations } from "./types";
export const translationContext = React.createContext<Translations | undefined>(
  undefined,
);
