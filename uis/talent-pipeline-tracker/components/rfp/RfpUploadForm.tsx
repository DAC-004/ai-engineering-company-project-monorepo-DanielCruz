"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/auth/types";
import { createRfpTicket } from "@/lib/rfp";

export const RfpUploadForm = () => {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setFormError("Choose a PDF request.");
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setFormError("Only a PDF request can be uploaded.");
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const created = await createRfpTicket(selectedFile);
      router.push(`/backoffice/rfp/${created.ticket_id}`);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "The upload could not be started.";
      setFormError(message);
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="rfp-file">RFP PDF</label>
        <input
          id="rfp-file"
          name="file"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            setSelectedFile(event.target.files?.[0] ?? null);
            setFormError(null);
          }}
        />
      </div>
      {formError ? <p className="form-error">{formError}</p> : null}
      <button className="btn-primary" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Uploading" : "Upload request"}
      </button>
    </form>
  );
};
