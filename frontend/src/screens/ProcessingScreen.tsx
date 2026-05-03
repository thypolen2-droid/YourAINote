import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { Screen } from './Screen';
import { useAppPreferences } from '../preferences/PreferencesContext';
import { AppTheme } from '../theme/themes';

export function ProcessingScreen() {
  const { t } = useTranslation();
  const { theme } = useAppPreferences();
  const styles = createStyles(theme);

  return (
    <Screen>
      <View style={styles.card}>
        <View style={styles.loaderShell}>
          <ActivityIndicator color={theme.primary} size="large" />
        </View>
        <Text style={styles.title}>{t('processing')}</Text>
        <Text style={styles.text}>{t('processing_hint')}</Text>
      </View>
    </Screen>
  );
}

const createStyles = (theme: AppTheme) => StyleSheet.create({
  card: {
    alignItems: 'center',
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 30,
    borderWidth: 1,
    gap: 16,
    justifyContent: 'center',
    minHeight: 320,
    padding: 28,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 18 },
    shadowOpacity: theme.name === 'dark' ? 0.24 : 0.1,
    shadowRadius: 30,
    elevation: 7,
  },
  loaderShell: {
    alignItems: 'center',
    backgroundColor: theme.primarySoft,
    borderRadius: 999,
    height: 88,
    justifyContent: 'center',
    width: 88,
  },
  title: {
    color: theme.text,
    fontSize: 26,
    fontWeight: '900',
  },
  text: {
    color: theme.subtext,
    fontSize: 16,
    lineHeight: 22,
    textAlign: 'center',
  },
});
