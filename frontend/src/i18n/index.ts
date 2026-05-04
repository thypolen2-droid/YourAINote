import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from '../../locales/en.json';
import km from '../../locales/km.json';

export const resources = {
  en: {
    translation: en,
  },
  km: {
    translation: km,
  },
} as const;

i18n.use(initReactI18next).init({
  compatibilityJSON: 'v4',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
  lng: 'en',
  resources,
});

export default i18n;
