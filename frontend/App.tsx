import './src/i18n';

import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { Text } from 'react-native';
import { useTranslation } from 'react-i18next';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { RootTabParamList } from './src/navigation/types';
import { PreferencesProvider, useAppPreferences } from './src/preferences/PreferencesContext';
import { HomeScreen } from './src/screens/HomeScreen';
import { NoteResultScreen } from './src/screens/NoteResultScreen';
import { ProcessingScreen } from './src/screens/ProcessingScreen';
import { RecordScreen } from './src/screens/RecordScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';

const Tab = createBottomTabNavigator<RootTabParamList>();

function AppTabs() {
  const { activeThemeName, theme } = useAppPreferences();
  const { t } = useTranslation();
  const baseTheme = activeThemeName === 'dark' ? DarkTheme : DefaultTheme;
  const navigationTheme = {
    ...baseTheme,
    colors: {
      ...baseTheme.colors,
      primary: theme.primary,
      background: theme.background,
      card: theme.card,
      text: theme.text,
      border: theme.border,
      notification: theme.primary,
    },
  };

  return (
    <NavigationContainer theme={navigationTheme}>
      <StatusBar style={activeThemeName === 'dark' ? 'light' : 'dark'} />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ color, focused }) => {
            const iconLabels: Record<keyof RootTabParamList, string> = {
              Home: 'H',
              Record: 'R',
              Processing: 'P',
              Result: 'N',
              Settings: 'S',
            };
            const iconLabel = iconLabels[route.name as keyof RootTabParamList];

            return (
              <Text
                style={{
                  color,
                  fontSize: focused ? 13 : 12,
                  fontWeight: '900',
                  lineHeight: 18,
                }}
              >
                {iconLabel}
              </Text>
            );
          },
          headerStyle: {
            backgroundColor: theme.background,
          },
          headerShadowVisible: false,
          headerTitleStyle: {
            color: theme.text,
            fontSize: 19,
            fontWeight: '800',
          },
          tabBarActiveTintColor: theme.primary,
          tabBarInactiveTintColor: theme.subtext,
          tabBarLabelStyle: {
            fontSize: 12,
            fontWeight: '800',
          },
          tabBarStyle: {
            backgroundColor: theme.card,
            borderTopColor: theme.border,
            borderTopWidth: 1,
            height: 78,
            paddingBottom: 18,
            paddingTop: 9,
            shadowColor: theme.shadow,
            shadowOffset: { width: 0, height: -8 },
            shadowOpacity: activeThemeName === 'dark' ? 0.22 : 0.08,
            shadowRadius: 18,
            elevation: 12,
          },
        })}
      >
        <Tab.Screen name="Home" component={HomeScreen} options={{ title: t('home') }} />
        <Tab.Screen name="Record" component={RecordScreen} options={{ title: t('record') }} />
        <Tab.Screen
          name="Processing"
          component={ProcessingScreen}
          options={{ title: t('processing') }}
        />
        <Tab.Screen
          name="Result"
          component={NoteResultScreen}
          options={{ title: t('note_result') }}
        />
        <Tab.Screen name="Settings" component={SettingsScreen} options={{ title: t('settings') }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <PreferencesProvider>
        <AppTabs />
      </PreferencesProvider>
    </SafeAreaProvider>
  );
}
