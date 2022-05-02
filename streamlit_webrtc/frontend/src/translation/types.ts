export interface Translations {
  start: string | null;
  stop: string | null;
  select_device: string | null;
  media_api_not_available: string | null;
  device_ask_permission: string | null;
  device_not_available: string | null;
  device_access_denied: string | null;
}
export type TranslationKey = keyof Translations;
