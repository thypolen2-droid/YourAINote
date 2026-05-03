import { PropsWithChildren } from 'react';
import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAppPreferences } from '../preferences/PreferencesContext';

export function Screen({ children }: PropsWithChildren) {
  const { theme } = useAppPreferences();
  const styles = createStyles(theme.background);

  return (
    <SafeAreaView edges={['left', 'right', 'bottom']} style={styles.safeArea}>
      <View style={styles.page}>{children}</View>
    </SafeAreaView>
  );
}

const createStyles = (backgroundColor: string) => StyleSheet.create({
  safeArea: {
    backgroundColor,
    flex: 1,
  },
  page: {
    flex: 1,
    gap: 18,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
});
