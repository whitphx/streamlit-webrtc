import React from "react";
import Button, { ButtonProps } from "@mui/material/Button";
import { useTranslation } from "../TranslationProvider";
import { TranslationKey } from "../types";

interface TranslatedButtonProps extends ButtonProps {
  translationKey: TranslationKey;
  defaultText: string;
}
const TranslatedButton: React.VFC<TranslatedButtonProps> = ({
  translationKey,
  defaultText,
  ...props
}) => {
  return (
    <Button {...props}>{useTranslation(translationKey) || defaultText}</Button>
  );
};

export default TranslatedButton;
