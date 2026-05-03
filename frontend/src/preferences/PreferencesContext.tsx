import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';

import { sendHeartbeat } from '../api/notes';
import i18n from '../i18n';
import { AppTheme, AppThemeName, themes } from '../theme/themes';

export type ThemePreference = AppThemeName | 'system';
export type LanguagePreference = 'en' | 'km';
export type BackendConnectionStatus = 'checking' | 'connected' | 'offline';

type PreferencesContextValue = {
  activeThemeName: AppThemeName;
  backendStatus: BackendConnectionStatus;
  backendUrl: string;
  language: LanguagePreference;
  onlineUsers: number;
  setBackendUrl: (url: string) => Promise<void>;
  setLanguage: (language: LanguagePreference) => Promise<void>;
  setThemePreference: (theme: ThemePreference) => Promise<void>;
  theme: AppTheme;
  themePreference: ThemePreference;
};

const THEME_STORAGE_KEY = 'yournoteai.theme';
const LANGUAGE_STORAGE_KEY = 'yournoteai.language';
const BACKEND_URL_STORAGE_KEY = 'yournoteai.backendUrl';
const CLIENT_ID_STORAGE_KEY = 'yournoteai.clientId';
const HEARTBEAT_INTERVAL_MS = 15000;
const LEGACY_LOCAL_BACKEND_URLS = new Set([
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8000/',
  'http://localhost:8000',
  'http://localhost:8000/',
  'http://10.0.2.2:8000',
  'http://10.0.2.2:8000/',
]);
const DEFAULT_BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL ?? 'http://127.0.0.1:8000';

function getInitialBackendUrl(storedBackendUrl: string | null) {
  if (!storedBackendUrl || LEGACY_LOCAL_BACKEND_URLS.has(storedBackendUrl)) {
    return DEFAULT_BACKEND_URL;
  }

  return storedBackendUrl;
}

function createClientId() {
  return `client-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const PreferencesContext = createContext<PreferencesContextValue | undefined>(undefined);

export function PreferencesProvider({ children }: PropsWithChildren) {
  const colorScheme = useColorScheme();
  const [backendUrl, setBackendUrlState] = useState(DEFAULT_BACKEND_URL);
  const [backendStatus, setBackendStatus] = useState<BackendConnectionStatus>('checking');
  const [clientId, setClientId] = useState<string | null>(null);
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>('system');
  const [language, setLanguageState] = useState<LanguagePreference>('en');
  const [onlineUsers, setOnlineUsers] = useState(0);

  useEffect(() => {
    async function loadPreferences() {
      const [storedTheme, storedLanguage, storedBackendUrl] = await Promise.all([
        AsyncStorage.getItem(THEME_STORAGE_KEY),
        AsyncStorage.getItem(LANGUAGE_STORAGE_KEY),
        AsyncStorage.getItem(BACKEND_URL_STORAGE_KEY),
      ]);

      if (storedTheme === 'light' || storedTheme === 'dark' || storedTheme === 'system') {
        setThemePreferenceState(storedTheme);
      }

      if (storedLanguage === 'en' || storedLanguage === 'km') {
        setLanguageState(storedLanguage);
        await i18n.changeLanguage(storedLanguage);
      }

      const nextBackendUrl = getInitialBackendUrl(storedBackendUrl);
      setBackendUrlState(nextBackendUrl);

      if (nextBackendUrl !== storedBackendUrl) {
        await AsyncStorage.setItem(BACKEND_URL_STORAGE_KEY, nextBackendUrl);
      }
    }

    loadPreferences();
  }, []);

  useEffect(() => {
    async function loadClientId() {
      const storedClientId = await AsyncStorage.getItem(CLIENT_ID_STORAGE_KEY);

      if (storedClientId) {
        setClientId(storedClientId);
        return;
      }

      const nextClientId = createClientId();
      await AsyncStorage.setItem(CLIENT_ID_STORAGE_KEY, nextClientId);
      setClientId(nextClientId);
    }

    loadClientId();
  }, []);

  useEffect(() => {
    if (!clientId) {
      return;
    }

    let isMounted = true;
    const activeClientId = clientId;

    async function updateBackendStatus() {
      try {
        const status = await sendHeartbeat(backendUrl, activeClientId);

        if (!isMounted) {
          return;
        }

        setBackendStatus('connected');
        setOnlineUsers(status.online_users);
      } catch {
        if (!isMounted) {
          return;
        }

        setBackendStatus('offline');
        setOnlineUsers(0);
      }
    }

    setBackendStatus('checking');
    updateBackendStatus();
    const intervalId = setInterval(updateBackendStatus, HEARTBEAT_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [backendUrl, clientId]);

  const activeThemeName: AppThemeName =
    themePreference === 'system' ? (colorScheme === 'dark' ? 'dark' : 'light') : themePreference;

  const setThemePreference = async (nextTheme: ThemePreference) => {
    setThemePreferenceState(nextTheme);
    await AsyncStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  };

  const setLanguage = async (nextLanguage: LanguagePreference) => {
    setLanguageState(nextLanguage);
    await i18n.changeLanguage(nextLanguage);
    await AsyncStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
  };

  const setBackendUrl = async (nextUrl: string) => {
    setBackendUrlState(nextUrl);
    await AsyncStorage.setItem(BACKEND_URL_STORAGE_KEY, nextUrl);
  };

  const value = useMemo(
    () => ({
      activeThemeName,
      backendStatus,
      backendUrl,
      language,
      onlineUsers,
      setBackendUrl,
      setLanguage,
      setThemePreference,
      theme: themes[activeThemeName],
      themePreference,
    }),
    [activeThemeName, backendStatus, backendUrl, language, onlineUsers, themePreference],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function useAppPreferences() {
  const context = useContext(PreferencesContext);

  if (!context) {
    throw new Error('useAppPreferences must be used inside PreferencesProvider');
  }

  return context;
}
