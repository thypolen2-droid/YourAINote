# YourNoteAI Tasks

This file tracks the MVP implementation tasks for YourNoteAI. Use `Plan.md` for the full product plan and this file for day-to-day execution.

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Done
- `[!]` Blocked

## Priority Legend

- `P0` Required for MVP
- `P1` Important polish or reliability
- `P2` Nice to have after MVP

## Milestone 1: Project Setup

- [x] `P0` Create frontend Expo React Native app.
- [x] `P0` Create backend FastAPI app.
- [x] `P0` Add project folders:
  - `frontend/`
  - `backend/`
  - `backend/storage/audio/`
  - `backend/storage/transcripts/`
  - `backend/storage/summaries/`
- [x] `P0` Add backend health endpoint: `GET /api/health`.
- [x] `P0` Add SQLite database setup.
- [x] `P0` Add basic `notes` table.
- [x] `P0` Add app name: `YourNoteAI`.
- [x] `P1` Add basic README run instructions.

Acceptance:

- Backend starts locally.
- `GET /api/health` returns `{ "status": "ok" }`.
- Frontend app opens without crashing.

## Milestone 2: Mobile App Shell

- [x] `P0` Install and configure React Navigation.
- [x] `P0` Create Home screen.
- [x] `P0` Create Record screen.
- [x] `P0` Create Processing screen.
- [x] `P0` Create Note Result screen.
- [x] `P0` Create Settings screen.
- [x] `P0` Add bottom tab navigation.
- [x] `P1` Add consistent screen headers and spacing.

Acceptance:

- User can navigate between main screens.
- App layout feels simple and uncluttered.

## Milestone 3: Theme System

- [x] `P0` Define light theme colors.
- [x] `P0` Define dark theme colors.
- [x] `P0` Add system theme detection.
- [x] `P0` Store selected theme in AsyncStorage.
- [x] `P0` Add Settings controls for Light, Dark, and System.
- [x] `P0` Apply theme globally across all screens.
- [ ] `P1` Verify readable text contrast in both modes.

Acceptance:

- User can switch Light, Dark, and System modes.
- All screens update correctly after changing theme.

## Milestone 4: Language Support

- [x] `P0` Install and configure i18n.
- [x] `P0` Create `locales/en.json`.
- [x] `P0` Create `locales/km.json`.
- [x] `P0` Add required translation keys.
- [x] `P0` Store selected language in AsyncStorage.
- [x] `P0` Add Settings controls for English and Khmer.
- [x] `P0` Apply translations across all visible UI text.

Acceptance:

- User can switch between English and Khmer.
- Main screens update immediately or after app reload.

## Milestone 5: Recording and Playback

- [x] `P0` Request microphone permission.
- [x] `P0` Show friendly message when permission is denied.
- [x] `P0` Implement start recording.
- [x] `P0` Implement pause recording.
- [x] `P0` Implement stop recording.
- [x] `P0` Show recording timer.
- [x] `P0` Save temporary audio file on device.
- [x] `P0` Add preview playback.
- [x] `P1` Add clean iPhone Voice Memos-style recording layout.

Acceptance:

- User can record a voice note.
- User can stop and preview the recording before upload.

## Milestone 6: Backend Upload API

- [x] `P0` Add `POST /api/notes/upload`.
- [x] `P0` Accept multipart audio upload.
- [x] `P0` Accept language preference.
- [x] `P0` Generate unique note ID.
- [x] `P0` Save audio to `backend/storage/audio/`.
- [x] `P0` Create database record.
- [x] `P0` Set `expires_at = created_at + 24 hours`.
- [x] `P0` Return note ID and status.
- [x] `P1` Validate supported audio file types.
- [x] `P1` Add max audio size or duration guard.

Acceptance:

- Mobile app can upload a recorded audio file.
- Backend stores the file temporarily and creates a note row.

## Milestone 7: Mobile Upload Flow

- [x] `P0` Add configurable backend server URL in Settings.
- [x] `P0` Store backend URL in AsyncStorage.
- [x] `P0` Upload selected recording to backend.
- [x] `P0` Show Processing screen during upload.
- [x] `P0` Handle backend offline error.
- [x] `P0` Handle upload failed error.

Acceptance:

- User can upload audio from the mobile app to the local PC backend.
- User sees a clear error if backend is unreachable.

## Milestone 8: Speech-to-Text

- [x] `P0` Choose transcription tool: Faster-Whisper or whisper.cpp.
- [x] `P0` Add transcription service module.
- [x] `P0` Update note status to `transcribing`.
- [x] `P0` Run transcription after upload.
- [x] `P0` Save transcript to `backend/storage/transcripts/`.
- [x] `P0` Save transcript path in database.
- [x] `P0` Return transcript to app.
- [x] `P1` Handle transcription failed state.

Acceptance:

- Uploaded audio is converted to text.
- Transcript is available to the mobile app.

## Milestone 9: Ollama Summary

- [x] `P0` Confirm Ollama is running locally.
- [x] `P0` Pull or configure model `qwen2.5:7b`.
- [x] `P0` Add Ollama summary service module.
- [x] `P0` Use summary prompt from `Plan.md`.
- [x] `P0` Update note status to `summarizing`.
- [x] `P0` Save summary to `backend/storage/summaries/`.
- [x] `P0` Save summary path in database.
- [x] `P0` Return summary to app.
- [x] `P1` Handle summary failed state.

Acceptance:

- Backend generates a short summary from transcript text.
- Result includes short summary, key points, and action items when available.

## Milestone 10: Note Result Screen

- [x] `P0` Display original voice section.
- [x] `P0` Add audio play and pause.
- [x] `P0` Show audio duration.
- [x] `P0` Display transcript section.
- [x] `P0` Add copy transcript button.
- [x] `P0` Display summary section.
- [x] `P0` Add copy summary button.
- [x] `P0` Add segmented control: Voice, Text, Summary.
- [x] `P1` Add friendly empty and loading states.

Acceptance:

- User can clearly view and use all 3 outputs: voice, transcript, and summary.

## Milestone 11: Temporary Note History

- [x] `P0` Add backend endpoint to list active notes.
- [x] `P0` Only return notes where `expires_at` is in the future.
- [x] `P0` Display recent notes on Home screen.
- [x] `P0` Show note date and time.
- [x] `P0` Show processing status.
- [x] `P0` Open note result from history.
- [x] `P0` Add manual delete endpoint.
- [x] `P0` Add manual delete action in app.

Acceptance:

- Home screen shows only notes that have not expired.
- User can open or delete an active note.

## Milestone 12: Auto Delete After 24 Hours

- [x] `P0` Add cleanup job that runs every 1 hour.
- [x] `P0` Find expired notes.
- [x] `P0` Delete expired audio files.
- [x] `P0` Delete expired transcript files.
- [x] `P0` Delete expired summary files.
- [x] `P0` Delete expired database rows.
- [x] `P0` Ensure missing files do not crash cleanup.
- [x] `P1` Add cleanup logs.

Acceptance:

- No note data remains after 24 hours.
- Expired notes do not appear in the app.

## Milestone 13: Error Handling

- [x] `P0` Handle no microphone permission.
- [x] `P0` Handle backend offline.
- [x] `P0` Handle upload failed.
- [x] `P0` Handle transcription failed.
- [x] `P0` Handle summary failed.
- [x] `P0` Handle expired file.
- [x] `P0` Handle audio too long.
- [x] `P0` Handle unsupported audio format.
- [x] `P1` Keep all error messages short and friendly.

Acceptance:

- Common failures show clear user-facing messages.
- App does not crash during expected error states.

## Milestone 14: Testing

- [!] `P0` Test frontend recording.
- [!] `P0` Test frontend playback.
- [!] `P0` Test frontend upload.
- [x] `P0` Test language switching.
- [x] `P0` Test light and dark mode.
- [x] `P0` Test result screen.
- [x] `P0` Test settings screen.
- [x] `P0` Test backend audio upload.
- [x] `P0` Test backend transcription.
- [x] `P0` Test backend Ollama summary.
- [x] `P0` Test manual deletion.
- [x] `P0` Test 24-hour cleanup.
- [x] `P0` Test invalid files.
- [x] `P1` Test large audio files.

Acceptance:

- MVP flow works end to end.
- Privacy deletion behavior is verified.

## Milestone 15: MVP Release

- [ ] `P0` Confirm MVP includes voice recording.
- [ ] `P0` Confirm MVP includes upload to local backend.
- [ ] `P0` Confirm MVP includes original audio playback.
- [ ] `P0` Confirm MVP includes speech-to-text.
- [ ] `P0` Confirm MVP includes AI summary.
- [ ] `P0` Confirm MVP includes Khmer and English UI.
- [ ] `P0` Confirm MVP includes light and dark mode.
- [ ] `P0` Confirm MVP includes 24-hour auto delete.
- [ ] `P0` Confirm MVP includes simple settings page.
- [ ] `P0` Confirm excluded features are not included:
  - Login system
  - Cloud storage
  - Payment system
  - Team sharing
  - Public user accounts
  - Permanent note sync

Acceptance:

- User can record, upload, transcribe, summarize, view, and delete temporary notes.
- All note data is automatically deleted after 24 hours.

## Current Next Task

Start with Milestone 15:

1. Run real-device Expo Go recording/playback/upload test.
2. Confirm PC LAN backend URL works from the phone.
3. Confirm MVP feature list.
4. Confirm excluded features are not included.
5. Prepare final MVP release notes.
