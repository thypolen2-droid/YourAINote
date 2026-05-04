import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Screen } from './Screen';
import {
  deleteNote,
  listNotes,
  retryNote,
  UploadedNote,
  waitForNoteProcessing,
} from '../api/notes';
import { RootTabParamList } from '../navigation/types';
import { useAppPreferences } from '../preferences/PreferencesContext';
import { AppTheme } from '../theme/themes';

export function HomeScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation<BottomTabNavigationProp<RootTabParamList, 'Home'>>();
  const { backendUrl, language, theme } = useAppPreferences();
  const styles = createStyles(theme);
  const [notes, setNotes] = useState<UploadedNote[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [retryingNoteId, setRetryingNoteId] = useState<string | null>(null);
  const recoverableNotesCount = notes.filter((note) => isRecoverableNote(note)).length;

  const loadNotes = useCallback(async () => {
    setIsLoading(true);
    setMessage('');

    try {
      const activeNotes = await listNotes(backendUrl);
      setNotes(activeNotes);
    } catch {
      setMessage(t('load_notes_failed'));
    } finally {
      setIsLoading(false);
    }
  }, [backendUrl, t]);

  useFocusEffect(
    useCallback(() => {
      loadNotes();
    }, [loadNotes]),
  );

  const openNote = (note: UploadedNote) => {
    navigation.navigate('Result', { note });
  };

  const removeNote = async (noteId: string) => {
    try {
      await deleteNote(backendUrl, noteId);
      setNotes((currentNotes) => currentNotes.filter((note) => note.id !== noteId));
    } catch {
      Alert.alert(t('delete_note_failed'), t('delete_note_failed'));
    }
  };

  const retryRecoverableNote = async (note: UploadedNote) => {
    setRetryingNoteId(note.id);
    setMessage('');

    try {
      const queuedNote = await retryNote(backendUrl, note.id, note.language || language);
      setNotes((currentNotes) =>
        currentNotes.map((currentNote) =>
          currentNote.id === queuedNote.id ? queuedNote : currentNote,
        ),
      );
      navigation.navigate('Processing');
      const retriedNote = await waitForNoteProcessing({
        backendUrl,
        noteId: queuedNote.id,
      });
      setNotes((currentNotes) =>
        currentNotes.map((currentNote) =>
          currentNote.id === retriedNote.id ? retriedNote : currentNote,
        ),
      );

      if (retriedNote.status === 'completed') {
        navigation.navigate('Result', { note: retriedNote });
        return;
      }

      setMessage(t('retry_note_failed'));
      navigation.navigate('Home');
      Alert.alert(
        retriedNote.is_stale ? t('job_stuck') : t('job_failed'),
        retriedNote.is_stale ? t('job_stuck_hint') : t('retry_note_failed'),
      );
    } catch {
      navigation.navigate('Home');
      setMessage(t('retry_note_failed'));
      Alert.alert(t('job_failed'), t('retry_note_failed'));
    } finally {
      setRetryingNoteId(null);
    }
  };

  return (
    <Screen>
      <View style={styles.hero}>
        <View style={styles.heroAccent} />
        <View style={styles.heroText}>
          <Text style={styles.title}>{t('app_name')}</Text>
          <Text style={styles.subtitle}>{t('recent_notes_hint')}</Text>
          <View style={styles.statsRow}>
            <View style={styles.statPill}>
              <Text style={styles.statNumber}>{notes.length}</Text>
              <Text style={styles.statLabel}>{t('note_result')}</Text>
            </View>
            <View style={styles.statPill}>
              <View style={styles.liveDot} />
              <Text style={styles.statLabel}>{isLoading ? t('processing') : t('uploaded')}</Text>
            </View>
            {recoverableNotesCount > 0 ? (
              <View style={[styles.statPill, styles.failedStatPill]}>
                <View style={styles.failedDot} />
                <Text style={styles.failedStatLabel}>
                  {recoverableNotesCount} {t('needs_retry')}
                </Text>
              </View>
            ) : null}
          </View>
        </View>
        <Pressable
          disabled={isLoading}
          onPress={loadNotes}
          style={[styles.refreshButton, isLoading && styles.disabledButton]}
        >
          <Text style={styles.refreshButtonText}>{t('refresh')}</Text>
        </Pressable>
      </View>

      {message ? <Text style={styles.errorText}>{message}</Text> : null}

      <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
        {notes.length === 0 ? (
          <View style={styles.card}>
            <View style={styles.emptyMark}>
              <Text style={styles.emptyMarkText}>AI</Text>
            </View>
            <Text style={styles.cardTitle}>{t('no_notes_yet')}</Text>
            <Text style={styles.cardText}>{t('first_note_hint')}</Text>
          </View>
        ) : (
          notes.map((note) => {
            const hasFailed = isFailedNote(note);
            const hasStaleJob = isStaleNote(note);
            const isRecoverable = hasFailed || hasStaleJob;

            return (
              <View key={note.id} style={[styles.noteCard, isRecoverable && styles.failedNoteCard]}>
                <Pressable onPress={() => openNote(note)} style={styles.noteMain}>
                  <View style={styles.noteTopLine}>
                    <View style={[styles.noteIcon, isRecoverable && styles.failedNoteIcon]}>
                      <Text style={[styles.noteIconText, isRecoverable && styles.failedNoteIconText]}>
                        {isRecoverable ? '!' : 'N'}
                      </Text>
                    </View>
                    <Text style={[styles.statusPill, isRecoverable && styles.failedStatusPill]}>
                      {hasFailed ? t('job_failed') : hasStaleJob ? t('job_stuck') : note.status}
                    </Text>
                  </View>
                  <Text style={styles.noteTitle}>
                    {note.summary?.split('\n')[0] || t('original_voice')}
                  </Text>
                  <Text style={styles.noteMeta}>
                    {t('created')}: {new Date(note.created_at).toLocaleString()}
                  </Text>
                  {isRecoverable ? (
                    <View style={styles.failedMessage}>
                      <Text style={styles.failedMessageTitle}>
                        {hasStaleJob ? t('job_stuck') : t('job_failed')}
                      </Text>
                      <Text style={styles.failedMessageText}>
                        {hasStaleJob ? t('job_stuck_hint') : t('home_job_failed_hint')}
                      </Text>
                    </View>
                  ) : null}
                </Pressable>
                <View style={styles.noteActions}>
                  {isRecoverable ? (
                    <Pressable
                      disabled={retryingNoteId === note.id}
                      onPress={() => retryRecoverableNote(note)}
                      style={[
                        styles.smallButton,
                        styles.retryButton,
                        retryingNoteId === note.id && styles.disabledButton,
                      ]}
                    >
                      <Text style={styles.retryButtonText}>
                        {retryingNoteId === note.id ? t('processing') : t('try_again')}
                      </Text>
                    </Pressable>
                  ) : null}
                  <Pressable onPress={() => openNote(note)} style={styles.smallButton}>
                    <Text style={styles.smallButtonText}>{t('open')}</Text>
                  </Pressable>
                  <Pressable
                    onPress={() => removeNote(note.id)}
                    style={[styles.smallButton, styles.deleteButton]}
                  >
                    <Text style={styles.deleteButtonText}>{t('delete')}</Text>
                  </Pressable>
                </View>
              </View>
            );
          })
        )}
      </ScrollView>
    </Screen>
  );
}

function isFailedNote(note: UploadedNote) {
  return note.status.toLowerCase().includes('fail');
}

function isStaleNote(note: UploadedNote) {
  return Boolean(note.is_stale);
}

function isRecoverableNote(note: UploadedNote) {
  return isFailedNote(note) || isStaleNote(note);
}

const createStyles = (theme: AppTheme) => StyleSheet.create({
  hero: {
    alignItems: 'flex-start',
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 28,
    borderWidth: 1,
    gap: 14,
    justifyContent: 'space-between',
    overflow: 'hidden',
    padding: 20,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: theme.name === 'dark' ? 0.22 : 0.12,
    shadowRadius: 28,
    elevation: 6,
  },
  heroAccent: {
    backgroundColor: theme.primarySoft,
    borderBottomLeftRadius: 999,
    height: 130,
    position: 'absolute',
    right: -44,
    top: -48,
    width: 150,
  },
  heroText: {
    flex: 1,
    gap: 10,
  },
  title: {
    color: theme.text,
    fontSize: 34,
    fontWeight: '900',
    letterSpacing: 0,
  },
  subtitle: {
    color: theme.subtext,
    fontSize: 17,
    lineHeight: 25,
  },
  statsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingTop: 6,
  },
  statPill: {
    alignItems: 'center',
    backgroundColor: theme.surface,
    borderRadius: 999,
    flexDirection: 'row',
    gap: 7,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  statNumber: {
    color: theme.primary,
    fontSize: 14,
    fontWeight: '900',
  },
  statLabel: {
    color: theme.subtext,
    fontSize: 12,
    fontWeight: '800',
  },
  failedStatPill: {
    backgroundColor: theme.dangerSoft,
  },
  failedStatLabel: {
    color: theme.danger,
    fontSize: 12,
    fontWeight: '900',
  },
  liveDot: {
    backgroundColor: theme.accent,
    borderRadius: 999,
    height: 8,
    width: 8,
  },
  failedDot: {
    backgroundColor: theme.danger,
    borderRadius: 999,
    height: 8,
    width: 8,
  },
  refreshButton: {
    alignSelf: 'flex-start',
    backgroundColor: theme.primary,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  refreshButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  disabledButton: {
    opacity: 0.55,
  },
  errorText: {
    color: theme.danger,
    fontSize: 15,
    lineHeight: 21,
  },
  list: {
    gap: 12,
    paddingBottom: 28,
  },
  card: {
    alignItems: 'flex-start',
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 10,
    padding: 22,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: theme.name === 'dark' ? 0.18 : 0.07,
    shadowRadius: 22,
    elevation: 3,
  },
  emptyMark: {
    alignItems: 'center',
    backgroundColor: theme.primarySoft,
    borderRadius: 18,
    height: 52,
    justifyContent: 'center',
    marginBottom: 4,
    width: 52,
  },
  emptyMarkText: {
    color: theme.primary,
    fontSize: 16,
    fontWeight: '900',
  },
  cardTitle: {
    color: theme.text,
    fontSize: 22,
    fontWeight: '900',
  },
  cardText: {
    color: theme.subtext,
    fontSize: 16,
    lineHeight: 22,
  },
  noteCard: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderRadius: 22,
    borderWidth: 1,
    gap: 14,
    padding: 17,
    shadowColor: theme.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: theme.name === 'dark' ? 0.16 : 0.05,
    shadowRadius: 18,
    elevation: 2,
  },
  failedNoteCard: {
    borderColor: theme.danger,
  },
  noteMain: {
    gap: 8,
  },
  noteTopLine: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  noteIcon: {
    alignItems: 'center',
    backgroundColor: theme.primarySoft,
    borderRadius: 14,
    height: 34,
    justifyContent: 'center',
    width: 34,
  },
  noteIconText: {
    color: theme.primary,
    fontSize: 14,
    fontWeight: '900',
  },
  failedNoteIcon: {
    backgroundColor: theme.dangerSoft,
  },
  failedNoteIconText: {
    color: theme.danger,
  },
  statusPill: {
    backgroundColor: theme.surface,
    borderRadius: 999,
    color: theme.subtext,
    fontSize: 12,
    fontWeight: '800',
    overflow: 'hidden',
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  failedStatusPill: {
    backgroundColor: theme.dangerSoft,
    color: theme.danger,
  },
  noteTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
  },
  noteMeta: {
    color: theme.subtext,
    fontSize: 14,
    lineHeight: 20,
  },
  failedMessage: {
    backgroundColor: theme.dangerSoft,
    borderRadius: 16,
    gap: 4,
    marginTop: 4,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  failedMessageTitle: {
    color: theme.danger,
    fontSize: 15,
    fontWeight: '900',
  },
  failedMessageText: {
    color: theme.text,
    fontSize: 14,
    lineHeight: 20,
  },
  noteActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  smallButton: {
    alignItems: 'center',
    backgroundColor: theme.surface,
    borderRadius: 13,
    flex: 1,
    minWidth: 104,
    paddingVertical: 11,
  },
  smallButtonText: {
    color: theme.text,
    fontSize: 14,
    fontWeight: '800',
  },
  retryButton: {
    backgroundColor: theme.danger,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
  deleteButton: {
    backgroundColor: theme.dangerSoft,
  },
  deleteButtonText: {
    color: theme.danger,
    fontSize: 14,
    fontWeight: '800',
  },
});
