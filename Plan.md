# YourNoteAI Plan

## Project Overview

YourNoteAI is a minimal voice-note app for personal or small-scale use. A mobile app records voice notes and uploads them to a local PC backend, where the audio is transcribed and summarized with local AI tools.

The app must protect user privacy by storing all note data temporarily only. Audio files, transcripts, summaries, and database rows must be deleted automatically after 24 hours.

## Core Goals

- Record voice notes from a mobile app.
- Upload audio to a local PC backend.
- Convert original voice recordings to text.
- Generate short, useful summaries using Ollama.
- Support English and Khmer UI.
- Support light mode, dark mode, and system theme.
- Auto-delete all user data after 24 hours.
- Keep the UI simple, clean, and iPhone-style.

## Main Outputs

Each voice note must provide:

1. Original voice recording with playback.
2. Full transcript from the voice note.
3. Short AI-generated summary with key points and action items.

## Recommended Tech Stack

### Frontend

- React Native
- Expo
- Expo AV / Audio Recording
- AsyncStorage for local settings
- React Navigation
- i18n for Khmer and English language support

### Backend

- FastAPI
- Python
- SQLite
- Local file storage
- Faster-Whisper or whisper.cpp for speech-to-text
- Ollama for local AI summary
- Scheduled cleanup job for 24-hour deletion

### Local AI

Recommended Ollama model:

```txt
qwen2.5:7b
```

Alternative models:

- llama3.1:8b
- mistral:7b
- gemma2:9b

## System Architecture

```txt
Mobile App
  -> Record voice
  -> Upload audio to PC backend
  -> Backend saves file temporarily
  -> Whisper converts audio to text
  -> Ollama summarizes transcript
  -> Backend returns audio URL, transcript, and summary
  -> Data auto-deletes after 24 hours
```

## API Overview

### Health Check

```http
GET /api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

### Upload Note

```http
POST /api/notes/upload
```

Request fields:

- `audio`: audio file
- `language`: user language preference
- `created_at`: client creation timestamp

Backend behavior:

- Generate a note ID.
- Save audio temporarily.
- Create a database record.
- Set `expires_at` to 24 hours after creation.
- Run transcription.
- Run summarization.
- Return note data to the app.

Example response:

```json
{
  "id": "note_id",
  "audio_url": "/api/notes/note_id/audio",
  "transcript": "Full transcript text",
  "summary": "Generated summary text",
  "status": "completed",
  "expires_at": "2026-05-03T10:00:00Z"
}
```

## Database Model

`notes` table:

- `id`
- `audio_path`
- `transcript_path`
- `summary_path`
- `created_at`
- `expires_at`
- `status`

Suggested statuses:

- `uploaded`
- `transcribing`
- `summarizing`
- `completed`
- `failed`
- `expired`

## Storage Structure

```txt
storage/
  audio/
  transcripts/
  summaries/
```

## Phase 1: Project Setup

Goal: Create the basic frontend and backend structure.

Frontend tasks:

- Create Expo React Native project.
- Set up folder structure.
- Install React Navigation.
- Create basic screens:
  - Home
  - Record
  - Processing
  - Note Result
  - Settings
- Add app name: YourNoteAI.

Backend tasks:

- Create FastAPI project.
- Set up SQLite database.
- Create local storage folders:
  - `storage/audio`
  - `storage/transcripts`
  - `storage/summaries`
- Create health check endpoint: `GET /api/health`.

Deliverable: A working mobile app shell and backend server.

## Phase 2: UI Design System

Goal: Build a minimal iPhone-style interface.

UI style:

- Clean layout.
- Large readable text.
- Rounded cards.
- Soft shadows.
- Bottom tab navigation.
- Minimal buttons.
- No crowded UI.

Theme support:

- Light mode.
- Dark mode.
- System mode.

Theme settings:

- Light.
- Dark.
- Use system setting.

Light mode colors:

- Background: `#F9F9F9`
- Card: `#FFFFFF`
- Text: `#111111`
- Subtext: `#666666`
- Primary: `#007AFF`

Dark mode colors:

- Background: `#000000`
- Card: `#1C1C1E`
- Text: `#FFFFFF`
- Subtext: `#A1A1A6`
- Primary: `#0A84FF`

Deliverable: App supports light and dark mode globally.

## Phase 3: Language Support

Goal: Add Khmer and English UI language support.

Supported languages:

- English
- Khmer

User settings:

- English
- ភាសាខ្មែរ

Translation files:

```txt
locales/en.json
locales/km.json
```

Required translation keys:

```json
{
  "app_name": "YourNoteAI",
  "start_recording": "Start Recording",
  "stop_recording": "Stop Recording",
  "processing": "Processing...",
  "transcript": "Transcript",
  "summary": "Summary",
  "original_voice": "Original Voice",
  "settings": "Settings",
  "language": "Language",
  "theme": "Theme"
}
```

Deliverable: User can switch between Khmer and English.

## Phase 4: Voice Recording

Goal: Allow users to record voice notes from the mobile app.

Features:

- Start recording.
- Pause recording.
- Stop recording.
- Show timer.
- Save temporary audio file on device.
- Preview playback before upload.

Record screen target:

```txt
00:01:24

[ Pause ]   [ Stop ]
```

Deliverable: User can record and preview voice audio.

## Phase 5: Audio Upload

Goal: Send recorded audio from the mobile app to the backend PC.

Endpoint:

```http
POST /api/notes/upload
```

Request:

- Audio file.
- Language preference.
- Created timestamp.

Backend behavior:

- Receive audio file.
- Generate note ID.
- Save audio temporarily.
- Create database record.
- Set expiration time to 24 hours.

Deliverable: Audio uploads successfully to backend.

## Phase 6: Speech-to-Text

Goal: Convert original voice into text.

Tool options:

- Faster-Whisper.
- whisper.cpp.

Backend flow:

```txt
Receive audio
  -> Run Whisper transcription
  -> Save transcript
  -> Update database status
  -> Return transcript
```

Response:

```json
{
  "id": "note_id",
  "transcript": "Full transcript text"
}
```

Deliverable: Uploaded audio is converted into text.

## Phase 7: AI Summary With Ollama

Goal: Generate a clean summary from the transcript.

Recommended model:

```txt
qwen2.5:7b
```

Summary prompt:

```txt
Summarize this voice note clearly.
Keep it short, useful, and easy to understand.
Return:
1. Short Summary
2. Key Points
3. Action Items if any

Text:
{{transcript}}
```

Backend flow:

```txt
Transcript
  -> Send to Ollama
  -> Receive summary
  -> Save summary
  -> Return result to app
```

Deliverable: Each note gets an AI-generated summary.

## Phase 8: Note Result Screen

Goal: Show the final processed note clearly.

Sections:

- Original Voice
  - Audio player.
  - Play / pause.
  - Duration.
- Transcript
  - Full original voice-to-text result.
  - Copy button.
- Summary
  - Short summary.
  - Key points.
  - Action items.
  - Copy button.

UI layout:

```txt
[ Voice ] [ Text ] [ Summary ]
```

Deliverable: User can view all 3 outputs clearly.

## Phase 9: Temporary Note History

Goal: Show notes created within the last 24 hours only.

Features:

- List recent notes.
- Show note date and time.
- Show processing status.
- Open note result.
- Delete note manually.

Important rule: Notes older than 24 hours must not appear.

Deliverable: Home screen shows only active temporary notes.

## Phase 10: Auto Delete After 24 Hours

Goal: Protect privacy by deleting all note data after 24 hours.

Backend rule:

```txt
expires_at = created_at + 24 hours
```

Cleanup job:

- Run every 1 hour.
- Find all notes where `expires_at` is older than the current time.
- Delete audio file.
- Delete transcript file.
- Delete summary file.
- Delete database row.

Deliverable: No user data remains after 24 hours.

## Phase 11: Settings Screen

Goal: Allow users to control app preferences.

Settings:

- Language:
  - English
  - Khmer
- Theme:
  - Light
  - Dark
  - System
- Backend Server URL:
  - Example: `http://192.168.1.10:8000`
- Privacy info:
  - Explain that all data auto-deletes after 24 hours.

Deliverable: User can configure language, theme, and backend URL.

## Phase 12: Error Handling

Goal: Make the app reliable and easy to understand.

Required error states:

- No microphone permission.
- Backend offline.
- Upload failed.
- Transcription failed.
- Summary failed.
- File expired.
- Audio too long.
- Unsupported audio format.

Message style:

- Keep messages short and friendly.
- Example: `Backend is offline. Please check your PC server.`

Deliverable: App handles errors cleanly.

## Phase 13: Testing

Frontend testing:

- Recording.
- Playback.
- Upload.
- Language switch.
- Light/dark mode.
- Result screen.
- Settings screen.

Backend testing:

- Audio upload.
- Whisper transcription.
- Ollama summary.
- 24-hour deletion.
- Manual deletion.
- Invalid files.
- Large audio files.

Privacy testing:

- Confirm audio deletes.
- Confirm transcript deletes.
- Confirm summary deletes.
- Confirm database row deletes.

Deliverable: App is stable for MVP use.

## Phase 14: MVP Release

MVP features:

- Voice recording.
- Upload to local backend.
- Original audio playback.
- Speech-to-text.
- AI summary.
- Khmer/English UI.
- Light/dark mode.
- 24-hour auto delete.
- Simple settings page.

Not included in MVP:

- Login system.
- Cloud storage.
- Payment system.
- Team sharing.
- Public user accounts.
- Permanent note sync.

Final MVP requirements:

- User can record voice.
- User can upload audio to backend.
- Backend transcribes audio.
- Backend summarizes transcript with Ollama.
- App displays original voice, transcript, and summary.
- User can switch Khmer/English.
- User can switch light/dark mode.
- All note data deletes after 24 hours.
- UI feels minimal and iPhone-style.

## Suggested MVP Build Order

1. Create backend health check, database, and storage folders.
2. Create Expo app shell with navigation and settings storage.
3. Add theme and language support.
4. Build recording and local playback.
5. Add upload endpoint and mobile upload flow.
6. Add transcription.
7. Add Ollama summary.
8. Build result screen.
9. Build temporary note history.
10. Add manual delete and scheduled cleanup.
11. Add error states.
12. Test the complete flow end to end.

## MVP Acceptance Checklist

- [ ] Mobile app opens to a clean YourNoteAI home screen.
- [ ] User can configure backend URL.
- [ ] User can switch English and Khmer UI.
- [ ] User can switch light, dark, and system themes.
- [ ] User can record audio.
- [ ] User can preview recorded audio.
- [ ] User can upload audio to backend.
- [ ] Backend stores uploaded files temporarily.
- [ ] Backend creates note records with `expires_at`.
- [ ] Backend transcribes audio successfully.
- [ ] Backend summarizes transcript with Ollama.
- [ ] App displays voice, transcript, and summary.
- [ ] App lists only notes from the last 24 hours.
- [ ] User can manually delete a note.
- [ ] Cleanup job deletes expired audio files.
- [ ] Cleanup job deletes expired transcript files.
- [ ] Cleanup job deletes expired summary files.
- [ ] Cleanup job deletes expired database rows.
- [ ] App shows friendly errors for common failure states.

