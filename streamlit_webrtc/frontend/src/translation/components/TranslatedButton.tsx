import Button, { ButtonProps } from "@mui/material/Button";
import { useTranslation } from "../useTranslation";
import { TranslationKey } from "../types";

interface TranslatedButtonProps extends ButtonProps {
  translationKey: TranslationKey;
  defaultText: string;
}
function TranslatedButton({
  translationKey,
  defaultText,
  ...props
}: TranslatedButtonProps) {
  return (
    <Button {...props}>{useTranslation(translationKey) || defaultText}</Button>
  );
}

export default TranslatedButton;
