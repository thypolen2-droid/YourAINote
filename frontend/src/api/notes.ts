export type UploadedNote = {
  id: string;
  audio_url: string;
  bytes: number;
  created_at: string;
  expires_at: string;
  language: string;
  status: string;
  summary?: string;
  transcript?: string;
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

function getAudioFileName(uri: string) {
  const fallbackName = `voice-note-${Date.now()}.m4a`;
  const uriName = uri.split('/').pop()?.split('?')[0];

  return uriName && uriName.includes('.') ? uriName : fallbackName;
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
    type: 'audio/mp4',
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

export async function deleteNote(backendUrl: string, noteId: string): Promise<void> {
  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/notes/${noteId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const detail = await parseApiError(response, 'Could not delete note.');
    throw new Error(detail);
  }
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
