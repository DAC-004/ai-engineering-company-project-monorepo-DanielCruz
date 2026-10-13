"use client";

import { FormEvent, useRef, useState } from "react";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import { ApiError } from "@/lib/auth/types";
import {
  analyzeIncidentCsv,
  downloadIncidentResultsCsv,
  type IncidentAnalysisResult,
} from "@/lib/incidentAnalyzer";

const INVALID_LABELS: Record<string, string> = {
  invalid_clinic_id: "Invalid or missing clinic_id",
  country_clinic_mismatch: "Country/clinic mismatch",
  invalid_category: "Invalid or missing category",
  empty_description: "Empty description",
  missing_patient_id: "Missing patient_id",
  closed_without_score: "Closed case, no score",
  score_out_of_range: "Satisfaction score out of range",
};

const SCORE_LABELS: Record<number, string> = {
  1: "Very dissatisfied",
  2: "Dissatisfied",
  3: "Neutral",
  4: "Satisfied",
  5: "Very satisfied",
};

const RULE_ORDER = [
  "invalid_clinic_id",
  "country_clinic_mismatch",
  "invalid_category",
  "empty_description",
  "missing_patient_id",
  "closed_without_score",
  "score_out_of_range",
] as const;

const pct = (part: number, whole: number) =>
  whole > 0 ? `${((part / whole) * 100).toFixed(1)}%` : "0.0%";

export const IncidentAnalysisPanel = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusKind, setStatusKind] = useState<"" | "ok" | "error">("");
  const [results, setResults] = useState<IncidentAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [lastFailedAction, setLastFailedAction] = useState<"analyze" | "export" | null>(
    null,
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const setStatus = (message: string, kind: "" | "ok" | "error" = "") => {
    setStatusMessage(message);
    setStatusKind(kind);
  };

  const handleAnalyze = async () => {
    const file = selectedFile ?? fileInputRef.current?.files?.[0] ?? null;
    if (!file) {
      setErrorMessage("Choose a CSV file before analyzing.");
      setLastFailedAction("analyze");
      setStatus("Choose a CSV file before analyzing.", "error");
      return;
    }

    setIsAnalyzing(true);
    setErrorMessage(null);
    setLastFailedAction(null);
    setStatus("Queuing analysis…");

    try {
      const payload = await analyzeIncidentCsv(file, (lifecycle) => {
        if (lifecycle === "pending") {
          setStatus("Waiting for worker…");
          return;
        }
        if (lifecycle === "started") {
          setStatus("Analyzing…");
        }
      });
      setResults(payload);
      setStatus(
        payload.invalid_count > 0
          ? `Analysis complete. ${payload.invalid_count} invalid record(s) found.`
          : "Analysis complete. No invalid records.",
        "ok",
      );
    } catch (error) {
      setResults(null);
      const message =
        error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
      setErrorMessage(message);
      setLastFailedAction("analyze");
      setStatus(message, "error");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExport = async () => {
    if (!results) {
      return;
    }

    setIsExporting(true);
    setErrorMessage(null);
    setLastFailedAction(null);
    setStatus("Exporting…");

    try {
      const { blob, filename } = await downloadIncidentResultsCsv();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus("Results CSV downloaded.", "ok");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
      setErrorMessage(message);
      setLastFailedAction("export");
      setStatus(message, "error");
    } finally {
      setIsExporting(false);
    }
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleAnalyze();
  };

  const validCount = results?.valid_count ?? 0;

  return (
    <section className="home-panel incident-analysis-panel">
      <p className="eyebrow">Patient Experience · Internal</p>
      <h1>Incident analysis</h1>
      <p className="home-lede">
        Upload the incident CSV to validate records, review category and status summaries, and
        export metrics. Patient identifiers are never shown in results.
      </p>

      <form className="incident-analysis-form" onSubmit={onSubmit}>
        <h2>Upload CSV</h2>
        <label className="incident-dropzone" htmlFor="incident-csv-input">
          <span className="incident-dropzone__title">Choose an incident CSV</span>
          <span className="incident-dropzone__file">
            {selectedFile?.name ?? "No file selected"}
          </span>
        </label>
        <input
          ref={fileInputRef}
          id="incident-csv-input"
          name="file"
          type="file"
          accept=".csv,text/csv"
          required
          onChange={(event) => {
            setSelectedFile(event.target.files?.[0] ?? null);
          }}
        />
        <div className="incident-analysis-actions">
          <button type="submit" className="btn-primary" disabled={isAnalyzing}>
            {isAnalyzing ? "Analyzing…" : "Analyze file"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!results || isExporting}
            onClick={() => void handleExport()}
          >
            {isExporting ? "Exporting…" : "Download results CSV"}
          </button>
        </div>
        <p
          className={
            statusKind === "error"
              ? "form-error"
              : statusKind === "ok"
                ? "form-success"
                : "field-hint"
          }
          role="status"
          aria-live="polite"
        >
          {statusMessage}
        </p>
        {errorMessage ? (
          <ErrorRecovery
            message={errorMessage}
            onRetry={() => {
              if (lastFailedAction === "export") {
                void handleExport();
                return;
              }
              void handleAnalyze();
            }}
          />
        ) : null}
      </form>

      {results ? (
        <section className="incident-analysis-results" aria-live="polite">
          <h2>Analysis summary</h2>
          <div className="incident-metric-grid">
            <div className="incident-metric">
              <strong>{results.total_records}</strong>
              <span>Total records</span>
            </div>
            <div className="incident-metric">
              <strong>{results.valid_count}</strong>
              <span>Valid</span>
            </div>
            <div className="incident-metric">
              <strong>{results.invalid_count}</strong>
              <span>Invalid</span>
            </div>
          </div>

          <div className="incident-analysis-panels">
            <article>
              <h3>Invalid records</h3>
              <ul>
                {results.invalid_count === 0 ? (
                  <li>
                    <span>No invalid records detected</span>
                    <strong>0</strong>
                  </li>
                ) : (
                  RULE_ORDER
                    .filter((key) => {
                      const count = results.invalid_by_rule[key] ?? 0;
                      return key !== "score_out_of_range" || count > 0;
                    })
                    .map((key) => (
                      <li key={key}>
                        <span>{INVALID_LABELS[key] ?? key}</span>
                        <strong>{results.invalid_by_rule[key] ?? 0}</strong>
                      </li>
                    ))
                )}
              </ul>
            </article>
            <article>
              <h3>By category</h3>
              <ul>
                {Object.entries(results.category_counts).map(([key, count]) => (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>{`${count} (${pct(count, validCount)})`}</strong>
                  </li>
                ))}
              </ul>
            </article>
            <article>
              <h3>By status</h3>
              <ul>
                {Object.entries(results.status_counts).map(([key, count]) => (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>{`${count} (${pct(count, validCount)})`}</strong>
                  </li>
                ))}
              </ul>
            </article>
            <article>
              <h3>By country</h3>
              <ul>
                {Object.entries(results.country_counts).map(([key, count]) => (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>{`${count} (${pct(count, validCount)})`}</strong>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <article className="incident-satisfaction">
            <h3>Satisfaction index (closed cases)</h3>
            <p>
              Scored cases: {results.satisfaction.scored_cases} of{" "}
              {results.satisfaction.closed_cases}. Average score:{" "}
              {results.satisfaction.average === null
                ? "n/a"
                : `${Number(results.satisfaction.average).toFixed(2)} / 5.00`}
            </p>
            <ul>
              {[1, 2, 3, 4, 5].map((score) => (
                <li key={score}>
                  <span>Score {score} ({SCORE_LABELS[score]})</span>
                  <strong>
                    {results.satisfaction.score_counts[String(score)] ?? 0}
                  </strong>
                </li>
              ))}
            </ul>
          </article>
        </section>
      ) : null}
    </section>
  );
};
