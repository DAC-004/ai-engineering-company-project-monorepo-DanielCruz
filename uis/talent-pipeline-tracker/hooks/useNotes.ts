"use client";

import { useCallback, useEffect, useState } from "react";

import { createNote, deleteNote, getNotes } from "@/lib/api/notes";
import type { Note } from "@/types/note";

interface UseNotesResult {
  notes: Note[];
  loading: boolean;
  error: string | null;
  isAdding: boolean;
  addError: string | null;
  addSuccess: string | null;
  deletingNoteId: string | null;
  deleteError: string | null;
  refetch: () => Promise<void>;
  addNote: (content: string) => Promise<boolean>;
  removeNote: (noteId: string) => Promise<boolean>;
}

export function useNotes(recordId: string): UseNotesResult {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addSuccess, setAddSuccess] = useState<string | null>(null);
  const [deletingNoteId, setDeletingNoteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function fetchNotes() {
      setLoading(true);
      setError(null);

      try {
        const response = await getNotes(recordId);

        if (isActive) {
          setNotes(response.data);
        }
      } catch (fetchError) {
        if (isActive) {
          const message =
            fetchError instanceof Error ? fetchError.message : "Failed to load notes.";
          setError(message);
          setNotes([]);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    void fetchNotes();

    return () => {
      isActive = false;
    };
  }, [recordId, reloadToken]);

  const refetch = useCallback(async () => {
    setReloadToken((current) => current + 1);
  }, []);

  const addNote = useCallback(
    async (content: string): Promise<boolean> => {
      setIsAdding(true);
      setAddError(null);
      setAddSuccess(null);

      try {
        await createNote(recordId, { content });
        setReloadToken((current) => current + 1);
        setAddSuccess("Note added successfully.");
        return true;
      } catch (submitError) {
        const message =
          submitError instanceof Error
            ? submitError.message
            : "Failed to add note.";
        setAddError(message);
        return false;
      } finally {
        setIsAdding(false);
      }
    },
    [recordId],
  );

  const removeNote = useCallback(
    async (noteId: string): Promise<boolean> => {
      setDeletingNoteId(noteId);
      setDeleteError(null);

      try {
        await deleteNote(recordId, noteId);
        setNotes((current) => current.filter((note) => note.id !== noteId));
        return true;
      } catch (submitError) {
        const message =
          submitError instanceof Error
            ? submitError.message
            : "Failed to delete note.";
        setDeleteError(message);
        return false;
      } finally {
        setDeletingNoteId(null);
      }
    },
    [recordId],
  );

  return {
    notes,
    loading,
    error,
    isAdding,
    addError,
    addSuccess,
    deletingNoteId,
    deleteError,
    refetch,
    addNote,
    removeNote,
  };
}
