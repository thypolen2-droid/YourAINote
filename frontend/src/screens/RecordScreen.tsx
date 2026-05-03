import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioPlayer,
  useAudioPlayerStatus,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useNavigation } from '@react-navigation/native';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Screen } from './Screen';
import { uploadNote } from '../api/notes';
import { RootTabParamList } from '../navigation/types';
import { useAppPreferences } from '../preferences/PreferencesContext';
import { AppTheme } from '../theme/themes';

function formatDuration(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return [hours, minutes, seconds].map((value) => value.toString().padStart(2, '0')).join(':');
}

function formatSeconds(seconds: number) {
  return formatDuration(seconds * 1000);
}

function getFriendlyUploadError(rawMessage: string, t: (key: string) => string) {
  if (rawMessage.includes('Unsupported audio format')) {
    return t('unsupported_audio_format');
  }

  if (rawMessage.includes('Audio file is too large')) {
    return t('audio_file_too_large');
  }

  if (rawMessage.includes('Audio too long')) {
    return t('audio_too_long');
  }

  if (rawMessage.includes('Transcription failed')) {
    return t('transcription_failed');
  }

  if (rawMessage.includes('Summary failed')) {
    return t('summary_failed');
  }

  if (rawMessage.includes('File expired')) {
    return t('file_expired');
  }

  return t('upload_failed');
}

export function RecordScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation<BottomTabNavigationProp<RootTabParamList, 'Record'>>();
  const { backendUrl, language, theme } = useAppPreferences();
  const styles = createStyles(theme);
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder, 250);
  const [recordingUri, setRecordingUri] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [message, setMessage] = useState(t('no_recording_preview'));
  const [isBusy, setIsBusy] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const player = useAudioPlayer(recordingUri ? { uri: recordingUri } : null, {
    updateInterval: 250,
  });
  const playerStatus = useAudioPlayerStatus(player);

  useEffect(() => {
    if (!recordingUri) {
      player.pause();
      return;
    }

    player.replace({ uri: recordingUri });
  }, [player, recordingUri]);

  const startRecording = async () => {
    setIsBusy(true);
    setMessage('');

    try {
      player.pause();
      if (recordingUri) {
        await player.seekTo(0);
      }

      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setMessage(t('microphone_permission_denied'));
        return;
      }

      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
      });
      setRecordingUri(null);
      setIsPaused(false);
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
    } catch (error) {
      setMessage(t('recording_error'));
    } finally {
      setIsBusy(false);
    }
  };

  const togglePauseRecording = () => {
    if (recorderState.isRecording) {
      audioRecorder.pause();
      setIsPaused(true);
      return;
    }

    if (isPaused) {
      audioRecorder.record();
      setIsPaused(false);
    }
  };

  const stopRecording = async () => {
    setIsBusy(true);

    try {
      await audioRecorder.stop();
      const uri = audioRecorder.uri ?? recorderState.url;
      setRecordingUri(uri);
      setIsPaused(false);
      setMessage(uri ? t('recording_ready') : t('recording_error'));
      await setAudioModeAsync({
        allowsRecording: false,
        playsInSilentMode: true,
      });
    } catch (error) {
      setMessage(t('recording_error'));
    } finally {
      setIsBusy(false);
    }
  };

  const togglePreview = async () => {
    if (!recordingUri) {
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

  const uploadRecording = async () => {
    if (!recordingUri) {
      return;
    }

    setIsUploading(true);
    setMessage(t('uploading'));
    player.pause();
    navigation.navigate('Processing');

    try {
      const note = await uploadNote({
        backendUrl,
        createdAt: new Date().toISOString(),
        language,
        uri: recordingUri,
      });

      setMessage(t('upload_ready'));
      navigation.navigate('Result', {
        note,
        recordingUri,
      });
    } catch (error) {
      const messageText =
        error instanceof TypeError
          ? t('backend_offline')
          : error instanceof Error
            ? getFriendlyUploadError(error.message, t)
            : t('upload_failed');
      setMessage(messageText);
      navigation.navigate('Record');
      Alert.alert(t('upload_failed'), messageText);
    } finally {
      setIsUploading(false);
    }
  };

  const hasActiveRecording = recorderState.isRecording || isPaused;
  const displayDuration = hasActiveRecording
    ? formatDuration(recorderState.durationMillis)
    : formatSeconds(playerStatus.duration || 0);
  const primaryLabel = hasActiveRecording ? t('new_recording') : t('start_recording');

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.recorder}>
          <View style={[styles.recordRing, hasActiveRecording && styles.recordRingActive]}>
            <View style={[styles.recordCore, hasActiveRecording && styles.recordCoreActive]} />
          </View>
          <Text style={styles.timer}>{displayDuration}</Text>
          <Text style={styles.helper}>{message || t('recording_placeholder')}</Text>
        </View>
        <View style={styles.actions}>
          <Pressable
            disabled={!hasActiveRecording || isBusy}
            onPress={togglePauseRecording}
            style={[
              styles.button,
              styles.secondaryButton,
              (!hasActiveRecording || isBusy) && styles.disabledButton,
            ]}
          >
            <Text style={[styles.buttonText, styles.secondaryText]}>
              {isPaused ? t('resume') : t('pause')}
            </Text>
          </Pressable>
          <Pressable
            disabled={!hasActiveRecording || isBusy}
            onPress={stopRecording}
            style={[styles.button, (!hasActiveRecording || isBusy) && styles.disabledButton]}
          >
            <Text style={styles.buttonText}>{t('stop')}</Text>
          </Pressable>
        </View>
        <View style={styles.actions}>
          <Pressable
            disabled={isBusy}
            onPress={startRecording}
            style={[styles.button, styles.fullButton, isBusy && styles.disabledButton]}
          >
            <Text style={styles.buttonText}>{primaryLabel}</Text>
          </Pressable>
        </View>
        <View style={styles.actions}>
          <Pressable
            disabled={!recordingUri || hasActiveRecording || isBusy || isUploading}
            onPress={uploadRecording}
            style={[
              styles.button,
              styles.fullButton,
              (!recordingUri || hasActiveRecording || isBusy || isUploading) && styles.disabledButton,
            ]}
          >
            <Text style={styles.buttonText}>{isUploading ? t('uploading') : t('upload')}</Text>
          </Pressable>
        </View>
        <View style={styles.previewCard}>
          <View style={styles.previewText}>
            <Text style={styles.previewTitle}>{t('preview')}</Text>
            <Text style={styles.previewSubtitle}>
              {recordingUri ? displayDuration : t('no_recording_preview')}
            </Text>
          </View>
          <Pressable
            disabled={!recordingUri || hasActiveRecording || isUploading}
            onPress={togglePreview}
            style={[
              styles.previewButton,
              (!recordingUri || hasActiveRecording || isUploading) && styles.disabledButton,
            ]}
          >
            <Text style={styles.previewButtonText}>
              {playerStatus.playing ? t('pause') : t('play')}
            </Text>
          </Pressable>
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
  recorder: {
    alignItems: 'center',
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 30,
    borderWidth: 1,
    gap: 14,
    justifyContent: 'center',
    minHeight: 310,
    padding: 24,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 18 },
    shadowOpacity: theme.name === 'dark' ? 0.26 : 0.11,
    shadowRadius: 30,
    elevation: 7,
  },
  recordRing: {
    alignItems: 'center',
    backgroundColor: theme.primarySoft,
    borderColor: theme.border,
    borderRadius: 999,
    borderWidth: 1,
    height: 112,
    justifyContent: 'center',
    marginBottom: 6,
    width: 112,
  },
  recordRingActive: {
    backgroundColor: theme.dangerSoft,
    borderColor: theme.danger,
  },
  recordCore: {
    backgroundColor: theme.primary,
    borderRadius: 999,
    height: 52,
    width: 52,
  },
  recordCoreActive: {
    backgroundColor: theme.danger,
  },
  timer: {
    color: theme.text,
    fontSize: 50,
    fontVariant: ['tabular-nums'],
    fontWeight: '900',
    letterSpacing: 0,
  },
  helper: {
    color: theme.subtext,
    fontSize: 16,
    lineHeight: 22,
    textAlign: 'center',
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
  },
  button: {
    alignItems: 'center',
    backgroundColor: theme.primary,
    borderRadius: 18,
    flex: 1,
    minHeight: 56,
    justifyContent: 'center',
    paddingHorizontal: 12,
    paddingVertical: 16,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: theme.name === 'dark' ? 0.16 : 0.08,
    shadowRadius: 16,
    elevation: 3,
  },
  secondaryButton: {
    backgroundColor: theme.surface,
    shadowOpacity: 0,
  },
  fullButton: {
    flex: 1,
  },
  disabledButton: {
    opacity: 0.45,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
  secondaryText: {
    color: theme.text,
  },
  previewCard: {
    alignItems: 'center',
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 22,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 16,
    justifyContent: 'space-between',
    padding: 19,
  },
  previewText: {
    flex: 1,
    gap: 4,
  },
  previewTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: '800',
  },
  previewSubtitle: {
    color: theme.subtext,
    fontSize: 15,
    lineHeight: 20,
  },
  previewButton: {
    alignItems: 'center',
    backgroundColor: theme.primary,
    borderRadius: 16,
    minWidth: 78,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  previewButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
  },
});
