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
    <section className="surface-card p-5 md:p-6 lg:p-8">
      <h3 className="text-xl font-semibold tracking-tight text-slate-900 md:text-2xl">
        Recruiter Notes
      </h3>
      <p className="mt-2 text-base leading-7 text-slate-600">
        Interview feedback and hiring observations for Diane Foster&apos;s team.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="flex flex-col gap-2">
          <span className="label-field">Add a note</span>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            rows={4}
            placeholder="Document interview feedback or hiring observations..."
            className="textarea-field"
          />
        </label>
        <button
          type="submit"
          disabled={isAdding || !content.trim()}
          className="btn-primary"
        >
          {isAdding ? "Adding note..." : "Add note"}
        </button>
      </form>

      {addSuccess ? (
        <div className="mt-5">
          <SuccessMessage message={addSuccess} />
        </div>
      ) : null}

      {addError ? (
        <div className="mt-5">
          <ErrorState message={addError} />
        </div>
      ) : null}

      <div className="mt-8 border-t border-slate-100 pt-6">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Activity log
        </h4>

        <div className="mt-4">
          {loading ? <LoadingState message="Loading notes..." /> : null}

          {!loading && error ? (
            <ErrorState message={error} onRetry={() => void refetch()} />
          ) : null}

          {!loading && !error && notes.length === 0 ? (
            <EmptyState title="No recruiter notes yet." />
          ) : null}

          {!loading && !error && notes.length > 0 ? (
            <ul className="space-y-4">
              {notes.map((note) => (
                <li
                  key={note.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-5"
                >
                  <p className="text-base leading-7 text-slate-800">
                    {note.content}
                  </p>
                  <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-200 pt-3">
                    <p className="text-sm text-slate-500">
                      {formatDate(note.created_at)}
                    </p>
                    <button
                      type="button"
                      onClick={() => void removeNote(note.id)}
                      disabled={deletingNoteId === note.id}
                      className="text-sm font-semibold text-rose-700 hover:text-rose-800 disabled:opacity-60"
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
      </div>
    </section>
  );
}
