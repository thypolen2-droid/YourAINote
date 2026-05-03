export type AppThemeName = 'light' | 'dark';

export const themes = {
  light: {
    name: 'light',
    background: '#F4F7FB',
    card: '#FFFFFF',
    surface: '#EEF3FA',
    elevated: '#FFFFFF',
    text: '#172033',
    subtext: '#647087',
    primary: '#3366FF',
    primarySoft: '#E8EEFF',
    accent: '#12B8A6',
    border: '#DEE6F1',
    control: '#E8EEF7',
    danger: '#E5484D',
    dangerSoft: '#FFECEE',
    success: '#18A058',
    warning: '#D98506',
    shadow: '#274060',
  },
  dark: {
    name: 'dark',
    background: '#0B1020',
    card: '#151B2E',
    surface: '#10172A',
    elevated: '#1D263D',
    text: '#F7FAFF',
    subtext: '#AAB5CA',
    primary: '#7AA2FF',
    primarySoft: '#1C2A52',
    accent: '#38D6C2',
    border: '#26324C',
    control: '#202A42',
    danger: '#FF6B75',
    dangerSoft: '#3B1D28',
    success: '#53D38B',
    warning: '#F2B84B',
    shadow: '#000000',
  },
} as const;

export type AppTheme = (typeof themes)[AppThemeName];
