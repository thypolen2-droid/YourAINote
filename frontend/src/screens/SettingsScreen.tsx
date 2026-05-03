import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { Screen } from './Screen';
import {
  LanguagePreference,
  ThemePreference,
  useAppPreferences,
} from '../preferences/PreferencesContext';
import { AppTheme } from '../theme/themes';

export function SettingsScreen() {
  const { t } = useTranslation();
  const {
    backendStatus,
    backendUrl,
    language,
    onlineUsers,
    setBackendUrl,
    setLanguage,
    setThemePreference,
    theme,
    themePreference,
  } = useAppPreferences();
  const styles = createStyles(theme);
  const backendStatusText =
    backendStatus === 'connected'
      ? t('backend_connected')
      : backendStatus === 'checking'
        ? t('backend_checking')
        : t('backend_offline_short');
  const themeOptions: { label: string; value: ThemePreference }[] = [
    { label: t('light'), value: 'light' },
    { label: t('dark'), value: 'dark' },
    { label: t('system'), value: 'system' },
  ];
  const languageOptions: { label: string; value: LanguagePreference }[] = [
    { label: t('english'), value: 'en' },
    { label: t('khmer'), value: 'km' },
  ];

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.heroCard}>
          <Text style={styles.heroTitle}>{t('settings')}</Text>
          <Text style={styles.heroText}>{t('privacy_24h')}</Text>
        </View>

        <View style={styles.group}>
          <Text style={styles.label}>{t('language')}</Text>
          <View style={styles.segmentedControl}>
            {languageOptions.map((option) => (
              <Pressable
                key={option.value}
                onPress={() => setLanguage(option.value)}
                style={[styles.segment, language === option.value && styles.activeSegment]}
              >
                <Text
                  style={[
                    styles.segmentText,
                    language === option.value && styles.activeSegmentText,
                  ]}
                >
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.group}>
          <Text style={styles.label}>{t('theme')}</Text>
          <View style={styles.segmentedControl}>
            {themeOptions.map((option) => (
              <Pressable
                key={option.value}
                onPress={() => setThemePreference(option.value)}
                style={[styles.segment, themePreference === option.value && styles.activeSegment]}
              >
                <Text
                  style={[
                    styles.segmentText,
                    themePreference === option.value && styles.activeSegmentText,
                  ]}
                >
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.group}>
          <Text style={styles.label}>{t('backend_server_url')}</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setBackendUrl}
            placeholder="http://192.168.1.10:8000"
            placeholderTextColor={theme.subtext}
            style={styles.input}
            value={backendUrl}
          />
        </View>
        <View style={styles.statusCard}>
          <View style={styles.statusHeader}>
            <View
              style={[
                styles.statusDot,
                backendStatus === 'connected' && styles.connectedDot,
                backendStatus === 'offline' && styles.offlineDot,
              ]}
            />
            <Text style={styles.statusTitle}>{backendStatusText}</Text>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>{t('backend_server_url')}</Text>
            <Text style={styles.statusValue}>{backendUrl}</Text>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>{t('online_users')}</Text>
            <Text style={styles.statusValue}>{onlineUsers}</Text>
          </View>
        </View>
        <View style={styles.card}>
          <Text style={styles.title}>{t('privacy')}</Text>
          <Text style={styles.text}>{t('privacy_24h')}</Text>
        </View>
      </ScrollView>
    </Screen>
  );
}

const createStyles = (theme: AppTheme) => StyleSheet.create({
  scrollContent: {
    gap: 18,
    paddingBottom: 28,
  },
  heroCard: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 26,
    borderWidth: 1,
    gap: 8,
    padding: 20,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: theme.name === 'dark' ? 0.2 : 0.08,
    shadowRadius: 24,
    elevation: 4,
  },
  heroTitle: {
    color: theme.text,
    fontSize: 28,
    fontWeight: '900',
  },
  heroText: {
    color: theme.subtext,
    fontSize: 15,
    lineHeight: 22,
  },
  group: {
    gap: 8,
  },
  label: {
    color: theme.text,
    fontSize: 16,
    fontWeight: '700',
  },
  segmentedControl: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    padding: 4,
  },
  segment: {
    alignItems: 'center',
    borderRadius: 14,
    flex: 1,
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: 10,
  },
  activeSegment: {
    backgroundColor: theme.card,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: theme.name === 'dark' ? 0.18 : 0.08,
    shadowRadius: 10,
    elevation: 2,
  },
  segmentText: {
    color: theme.subtext,
    fontSize: 15,
    fontWeight: '700',
  },
  activeSegmentText: {
    color: theme.text,
  },
  input: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 18,
    borderWidth: 1,
    color: theme.text,
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  statusCard: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 12,
    padding: 19,
  },
  statusHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  statusDot: {
    backgroundColor: theme.warning,
    borderRadius: 999,
    height: 11,
    width: 11,
  },
  connectedDot: {
    backgroundColor: theme.success,
  },
  offlineDot: {
    backgroundColor: theme.danger,
  },
  statusTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: '800',
  },
  statusRow: {
    gap: 4,
  },
  statusLabel: {
    color: theme.subtext,
    fontSize: 13,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  statusValue: {
    color: theme.text,
    fontSize: 15,
    lineHeight: 21,
  },
  card: {
    backgroundColor: theme.primarySoft,
    borderColor: theme.border,
    borderRadius: 22,
    borderWidth: 1,
    gap: 8,
    padding: 18,
  },
  title: {
    color: theme.text,
    fontSize: 20,
    fontWeight: '800',
  },
  text: {
    color: theme.subtext,
    fontSize: 16,
    lineHeight: 22,
  },
});
