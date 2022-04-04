import React from "react";
import Button, { ButtonProps } from "@mui/material/Button";
import { useTranslation } from "../TranslationProvider";
import { TranslationKey } from "../types";

interface TranslatedButtonProps extends ButtonProps {
  translationKey: TranslationKey;
}
const TranslatedButton: React.VFC<TranslatedButtonProps> = ({
  translationKey,
  ...props
}) => {
  return <Button {...props}>{useTranslation(translationKey)}</Button>;
};

export default TranslatedButton;
