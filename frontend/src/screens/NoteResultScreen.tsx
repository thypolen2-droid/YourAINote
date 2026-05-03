import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import * as Clipboard from 'expo-clipboard';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Screen } from './Screen';
import { RootTabParamList } from '../navigation/types';
import { useAppPreferences } from '../preferences/PreferencesContext';
import { AppTheme } from '../theme/themes';

type Props = BottomTabScreenProps<RootTabParamList, 'Result'>;
type ResultTab = 'voice' | 'text' | 'summary';

function formatSeconds(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;

  return `${minutes}:${remainder.toString().padStart(2, '0')}`;
}

export function NoteResultScreen({ route }: Props) {
  const { t } = useTranslation();
  const { backendUrl, theme } = useAppPreferences();
  const styles = createStyles(theme);
  const [activeTab, setActiveTab] = useState<ResultTab>('voice');
  const [copiedTab, setCopiedTab] = useState<ResultTab | null>(null);
  const note = route.params?.note;
  const recordingUri = route.params?.recordingUri;
  const audioUri = useMemo(() => {
    if (recordingUri) {
      return recordingUri;
    }

    if (note?.audio_url) {
      return `${backendUrl.replace(/\/$/, '')}${note.audio_url}`;
    }

    return null;
  }, [backendUrl, note?.audio_url, recordingUri]);
  const player = useAudioPlayer(audioUri ? { uri: audioUri } : null, {
    updateInterval: 250,
  });
  const playerStatus = useAudioPlayerStatus(player);
  const tabs: { label: string; value: ResultTab }[] = [
    { label: t('original_voice'), value: 'voice' },
    { label: t('transcript'), value: 'text' },
    { label: t('summary'), value: 'summary' },
  ];

  useEffect(() => {
    if (!audioUri) {
      player.pause();
      return;
    }

    player.replace({ uri: audioUri });
  }, [audioUri, player]);

  const copyText = async (tab: ResultTab, value: string | undefined) => {
    if (!value) {
      return;
    }

    await Clipboard.setStringAsync(value);
    setCopiedTab(tab);
    setTimeout(() => setCopiedTab(null), 1400);
  };

  const togglePlayback = async () => {
    if (!audioUri) {
      return;
    }

    if (playerStatus.playing) {
      player.pause();
      return;
    }

    if (playerStatus.didJustFinish) {
      await player.seekTo(0);
    }

    player.play();
  };

  const renderVoice = () => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.titleMark}>
          <Text style={styles.titleMarkText}>A</Text>
        </View>
        <Text style={styles.title}>{t('original_voice')}</Text>
      </View>
      {audioUri ? (
        <>
          <View style={styles.playbackRow}>
            <Pressable onPress={togglePlayback} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>
                {playerStatus.playing ? t('pause') : t('play')}
              </Text>
            </Pressable>
            <View style={styles.durationBlock}>
              <Text style={styles.detailLabel}>{t('duration')}</Text>
              <Text style={styles.detailValue}>{formatSeconds(playerStatus.duration || 0)}</Text>
            </View>
          </View>
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                {
                  width: `${Math.min(
                    100,
                    playerStatus.duration
                      ? (playerStatus.currentTime / playerStatus.duration) * 100
                      : 0,
                  )}%`,
                },
              ]}
            />
          </View>
        </>
      ) : (
        <Text style={styles.text}>{t('no_audio')}</Text>
      )}
      {note ? (
        <View style={styles.detailList}>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>{t('status')}</Text>
            <Text style={styles.detailValue}>{note.status}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>{t('note_id')}</Text>
            <Text style={styles.detailValue}>{note.id}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>{t('expires_at')}</Text>
            <Text style={styles.detailValue}>{new Date(note.expires_at).toLocaleString()}</Text>
          </View>
        </View>
      ) : null}
    </View>
  );

  const renderTextPanel = (
    tab: ResultTab,
    title: string,
    value: string | undefined,
    emptyMessage: string,
  ) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.titleMark}>
          <Text style={styles.titleMarkText}>{tab === 'summary' ? 'S' : 'T'}</Text>
        </View>
        <Text style={styles.title}>{title}</Text>
        <Pressable
          disabled={!value}
          onPress={() => copyText(tab, value)}
          style={[styles.copyButton, !value && styles.disabledButton]}
        >
          <Text style={styles.copyButtonText}>{copiedTab === tab ? t('copied') : t('copy')}</Text>
        </Pressable>
      </View>
      <Text style={value ? styles.contentText : styles.text}>{value || emptyMessage}</Text>
    </View>
  );

  return (
    <Screen>
      <View style={styles.segmentedControl}>
        {tabs.map((tab) => (
          <Pressable
            key={tab.value}
            onPress={() => setActiveTab(tab.value)}
            style={[styles.segment, activeTab === tab.value && styles.activeSegment]}
          >
            <Text style={[styles.segmentText, activeTab === tab.value && styles.activeSegmentText]}>
              {tab.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {activeTab === 'voice' && renderVoice()}
        {activeTab === 'text' &&
          renderTextPanel('text', t('transcript'), note?.transcript, t('no_transcript'))}
        {activeTab === 'summary' &&
          renderTextPanel('summary', t('summary'), note?.summary, t('no_summary'))}
      </ScrollView>
    </Screen>
  );
}

const createStyles = (theme: AppTheme) => StyleSheet.create({
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
    justifyContent: 'center',
    minHeight: 46,
    paddingHorizontal: 6,
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
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
  },
  activeSegmentText: {
    color: theme.text,
  },
  scrollContent: {
    paddingBottom: 28,
  },
  card: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 16,
    padding: 19,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: theme.name === 'dark' ? 0.2 : 0.07,
    shadowRadius: 24,
    elevation: 4,
  },
  cardHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'space-between',
  },
  titleMark: {
    alignItems: 'center',
    backgroundColor: theme.primarySoft,
    borderRadius: 14,
    height: 38,
    justifyContent: 'center',
    width: 38,
  },
  titleMarkText: {
    color: theme.primary,
    fontSize: 15,
    fontWeight: '900',
  },
  title: {
    color: theme.text,
    flex: 1,
    fontSize: 21,
    fontWeight: '900',
  },
  text: {
    color: theme.subtext,
    fontSize: 16,
    lineHeight: 22,
  },
  contentText: {
    color: theme.text,
    fontSize: 16,
    lineHeight: 24,
  },
  playbackRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 14,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: theme.primary,
    borderRadius: 17,
    minWidth: 92,
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  durationBlock: {
    flex: 1,
    gap: 3,
  },
  progressTrack: {
    backgroundColor: theme.surface,
    borderRadius: 999,
    height: 9,
    overflow: 'hidden',
  },
  progressFill: {
    backgroundColor: theme.primary,
    borderRadius: 999,
    height: '100%',
  },
  detailList: {
    borderTopColor: theme.border,
    borderTopWidth: 1,
    gap: 12,
    paddingTop: 14,
  },
  detailRow: {
    gap: 4,
  },
  detailLabel: {
    color: theme.subtext,
    fontSize: 13,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  detailValue: {
    color: theme.text,
    fontSize: 15,
    lineHeight: 21,
  },
  copyButton: {
    alignItems: 'center',
    backgroundColor: theme.surface,
    borderRadius: 15,
    minWidth: 76,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  copyButtonText: {
    color: theme.text,
    fontSize: 14,
    fontWeight: '800',
  },
  disabledButton: {
    opacity: 0.45,
  },
});
