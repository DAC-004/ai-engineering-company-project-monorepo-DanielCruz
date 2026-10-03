import { apiFetch } from "@/lib/api/client";
import type { NotesListResponse } from "@/types/api";
import type { Note, NoteCreateInput } from "@/types/note";

export async function getNotes(recordId: string): Promise<NotesListResponse> {
  return apiFetch<NotesListResponse>(`/records/${recordId}/notes`);
}

export async function createNote(
  recordId: string,
  input: NoteCreateInput,
): Promise<Note> {
  return apiFetch<Note>(`/records/${recordId}/notes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteNote(
  recordId: string,
  noteId: string,
): Promise<void> {
  await apiFetch<void>(`/records/${recordId}/notes/${noteId}`, {
    method: "DELETE",
  });
}
