export type UploadedNote = {
  id: string;
  audio_url: string;
  bytes: number;
  created_at: string;
  expires_at: string;
  is_stale?: boolean;
  language: string;
  status: string;
  summary?: string;
  transcript?: string;
  updated_at?: string;
};

export type BackendStatus = {
  online_users: number;
  status: string;
};

async function parseApiError(response: Response, fallback: string) {
  try {
    const errorBody = (await response.json()) as { detail?: string };
    return errorBody.detail ?? fallback;
  } catch {
    return fallback;
  }
}

type UploadNoteInput = {
  backendUrl: string;
  createdAt: string;
  language: string;
  uri: string;
};

type WaitForNoteProcessingInput = {
  backendUrl: string;
  intervalMs?: number;
  noteId: string;
  timeoutMs?: number;
};

const PROCESSING_STATUSES = new Set(['uploaded', 'transcribing', 'transcribed', 'summarizing']);
const DEFAULT_PROCESSING_INTERVAL_MS = 2000;
const DEFAULT_PROCESSING_TIMEOUT_MS = 10 * 60 * 1000;

const AUDIO_CONTENT_TYPES: Record<string, string> = {
  aac: 'audio/aac',
  caf: 'audio/x-caf',
  m4a: 'audio/mp4',
  mp3: 'audio/mpeg',
  mp4: 'audio/mp4',
  wav: 'audio/wav',
  webm: 'audio/webm',
};

const SUPPORTED_UPLOAD_EXTENSIONS = new Set(Object.keys(AUDIO_CONTENT_TYPES));

function delay(milliseconds: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

function isProcessingNote(note: UploadedNote) {
  return PROCESSING_STATUSES.has(note.status) && !note.is_stale;
}

function getAudioFileName(uri: string) {
  const fallbackName = `voice-note-${Date.now()}.m4a`;
  const uriName = uri.split('/').pop()?.split('?')[0];
  const extension = uriName?.split('.').pop()?.toLowerCase();

  return uriName && extension && SUPPORTED_UPLOAD_EXTENSIONS.has(extension) ? uriName : fallbackName;
}

function getAudioContentType(fileName: string) {
  const extension = fileName.split('.').pop()?.toLowerCase();

  return extension ? AUDIO_CONTENT_TYPES[extension] ?? 'audio/mp4' : 'audio/mp4';
}

export async function uploadNote({
  backendUrl,
  createdAt,
  language,
  uri,
}: UploadNoteInput): Promise<UploadedNote> {
  const formData = new FormData();
  const fileName = getAudioFileName(uri);

  formData.append('audio', {
    name: fileName,
    type: getAudioContentType(fileName),
    uri,
  } as unknown as Blob);
  formData.append('language', language);
  formData.append('created_at', createdAt);

  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes/upload`, {
    body: formData,
    method: 'POST',
  });

  if (!response.ok) {
    const detail = await parseApiError(response, 'Upload failed.');
    throw new Error(detail);
  }

  return response.json() as Promise<UploadedNote>;
}

export async function listNotes(backendUrl: string): Promise<UploadedNote[]> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes`);

  if (!response.ok) {
    const detail = await parseApiError(response, 'Could not load notes.');
    throw new Error(detail);
  }

  return response.json() as Promise<UploadedNote[]>;
}

export async function getNote(backendUrl: string, noteId: string): Promise<UploadedNote> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes/${noteId}`);

  if (!response.ok) {
    const detail = await parseApiError(response, 'Could not load note.');
    throw new Error(detail);
  }

  return response.json() as Promise<UploadedNote>;
}

export async function waitForNoteProcessing({
  backendUrl,
  intervalMs = DEFAULT_PROCESSING_INTERVAL_MS,
  noteId,
  timeoutMs = DEFAULT_PROCESSING_TIMEOUT_MS,
}: WaitForNoteProcessingInput): Promise<UploadedNote> {
  const deadline = Date.now() + timeoutMs;
  let latestNote = await getNote(backendUrl, noteId);

  while (isProcessingNote(latestNote) && Date.now() < deadline) {
    await delay(intervalMs);
    latestNote = await getNote(backendUrl, noteId);
  }

  return latestNote;
}

export async function deleteNote(backendUrl: string, noteId: string): Promise<void> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes/${noteId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const detail = await parseApiError(response, 'Could not delete note.');
    throw new Error(detail);
  }
}

export async function retryNote(
  backendUrl: string,
  noteId: string,
  language: string,
): Promise<UploadedNote> {
  const formData = new FormData();
  formData.append('language', language);

  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes/${noteId}/retry`, {
    body: formData,
    method: 'POST',
  });

  if (!response.ok) {
    const detail = await parseApiError(response, 'Upload failed.');
    throw new Error(detail);
  }

  return response.json() as Promise<UploadedNote>;
}

export async function getBackendStatus(backendUrl: string): Promise<BackendStatus> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/status`);

  if (!response.ok) {
    const detail = await parseApiError(response, 'Backend status check failed.');
    throw new Error(detail);
  }

  return response.json() as Promise<BackendStatus>;
}

export async function sendHeartbeat(
  backendUrl: string,
  clientId: string,
): Promise<BackendStatus> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/presence/heartbeat`, {
    body: JSON.stringify({ client_id: clientId }),
    headers: {
      'Content-Type': 'application/json',
    },
    method: 'POST',
  });

  if (!response.ok) {
    const detail = await parseApiError(response, 'Backend heartbeat failed.');
    throw new Error(detail);
  }

  return response.json() as Promise<BackendStatus>;
}
