"use client";

import { useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { SuccessMessage } from "@/components/ui/SuccessMessage";
import { useNotes } from "@/hooks/useNotes";
import { formatDate } from "@/lib/labels";

interface NotesSectionProps {
  recordId: string;
}

export function NotesSection({ recordId }: NotesSectionProps) {
  const [content, setContent] = useState("");
  const {
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
  } = useNotes(recordId);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!content.trim()) {
      return;
    }

    const success = await addNote(content.trim());
    if (success) {
      setContent("");
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900">Recruiter Notes</h3>
      <p className="mt-1 text-sm text-slate-600">
        Interview feedback and hiring observations for Diane Foster&apos;s team.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Add a note</span>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            rows={4}
            placeholder="Document interview feedback or hiring observations..."
            className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
        </label>
        <button
          type="submit"
          disabled={isAdding || !content.trim()}
          className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isAdding ? "Adding note..." : "Add note"}
        </button>
      </form>

      {addSuccess ? (
        <div className="mt-4">
          <SuccessMessage message={addSuccess} />
        </div>
      ) : null}

      {addError ? (
        <div className="mt-4">
          <ErrorState message={addError} />
        </div>
      ) : null}

      <div className="mt-6">
        {loading ? <LoadingState message="Loading notes..." /> : null}

        {!loading && error ? (
          <ErrorState message={error} onRetry={() => void refetch()} />
        ) : null}

        {!loading && !error && notes.length === 0 ? (
          <EmptyState title="No recruiter notes yet." />
        ) : null}

        {!loading && !error && notes.length > 0 ? (
          <ul className="space-y-3">
            {notes.map((note) => (
              <li
                key={note.id}
                className="rounded-lg border border-slate-200 bg-slate-50 p-4"
              >
                <p className="text-sm text-slate-800">{note.content}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    {formatDate(note.created_at)}
                  </p>
                  <button
                    type="button"
                    onClick={() => void removeNote(note.id)}
                    disabled={deletingNoteId === note.id}
                    className="text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-60"
                  >
                    {deletingNoteId === note.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}

        {deleteError ? (
          <div className="mt-4">
            <ErrorState message={deleteError} />
          </div>
        ) : null}
      </div>
    </section>
  );
}
