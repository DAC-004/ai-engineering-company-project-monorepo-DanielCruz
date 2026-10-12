(() => {
  const API_BASE = "http://127.0.0.1:8000";
  const SUPPORT_EMAIL = "care@healthcore.com";

  const INVALID_LABELS = {
    invalid_clinic_id: "Invalid or missing clinic_id",
    country_clinic_mismatch: "Country/clinic mismatch",
    invalid_category: "Invalid or missing category",
    empty_description: "Empty description",
    missing_patient_id: "Missing patient_id",
    closed_without_score: "Closed case, no score",
    score_out_of_range: "Satisfaction score out of range",
  };

  const SCORE_LABELS = {
    1: "Very dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very satisfied",
  };

  const form = document.getElementById("upload-form");
  const fileInput = document.getElementById("file-input");
  const dropzone = document.getElementById("dropzone");
  const fileName = document.getElementById("file-name");
  const statusMsg = document.getElementById("status-msg");
  const results = document.getElementById("results");
  const exportBtn = document.getElementById("export-btn");
  const analyzeBtn = document.getElementById("analyze-btn");
  const errorRecovery = document.getElementById("error-recovery");
  const retryBtn = document.getElementById("retry-btn");

  let selectedFile = null;
  let lastFailedAction = null;

  const setStatus = (message, kind = "") => {
    statusMsg.textContent = message;
    statusMsg.classList.remove("is-error", "is-ok");
    if (kind) statusMsg.classList.add(kind);
  };

  const hideRecovery = () => {
    lastFailedAction = null;
    errorRecovery.classList.add("is-hidden");
  };

  const showRecovery = (action) => {
    lastFailedAction = action;
    errorRecovery.classList.remove("is-hidden");
  };

  const toUserFacingFetchError = (response) => {
    if (!response) {
      return "Unable to reach the server. Check your connection and try again.";
    }
    if (response.status === 401) {
      return (
        "Sign-in is required to analyze incidents. Contact support at " +
        SUPPORT_EMAIL +
        " if you need access."
      );
    }
    if (response.status === 400) {
      return "The file could not be analyzed. Check that it is a valid CSV and try again.";
    }
    if (response.status === 404) {
      return "No analysis results are available yet. Analyze a CSV first.";
    }
    return (
      "Something went wrong. Please try again or contact support at " +
      SUPPORT_EMAIL +
      "."
    );
  };

  const pct = (part, whole) =>
    whole > 0 ? `${((part / whole) * 100).toFixed(1)}%` : "0.0%";

  const renderList = (element, entries) => {
    if (!element) return;
    element.innerHTML = entries
      .map(
        ([label, value]) =>
          `<li><span>${label}</span><strong>${value}</strong></li>`
      )
      .join("");
  };

  const renderResults = (data) => {
    const payload = data || {};
    const general = document.getElementById("general-metrics");
    if (general) {
      general.innerHTML = [
        ["Total records", payload.total_records ?? 0],
        ["Valid", payload.valid_count ?? 0],
        ["Invalid", payload.invalid_count ?? 0],
      ]
        .map(
          ([label, value]) =>
            `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`
        )
        .join("");
    }

    const ruleOrder = [
      "invalid_clinic_id",
      "country_clinic_mismatch",
      "invalid_category",
      "empty_description",
      "missing_patient_id",
      "closed_without_score",
      "score_out_of_range",
    ];
    const invalidEntries = ruleOrder
      .filter((key) => {
        const count = payload.invalid_by_rule?.[key] || 0;
        return key !== "score_out_of_range" || count > 0;
      })
      .map((key) => [
        INVALID_LABELS[key] || key,
        payload.invalid_by_rule?.[key] || 0,
      ]);

    if ((payload.invalid_count ?? 0) === 0) {
      renderList(document.getElementById("invalid-list"), [
        ["No invalid records detected", "0"],
      ]);
    } else {
      renderList(document.getElementById("invalid-list"), invalidEntries);
    }

    const validCount = payload.valid_count ?? 0;
    renderList(
      document.getElementById("category-list"),
      Object.entries(payload.category_counts || {}).map(([key, count]) => [
        key,
        `${count} (${pct(count, validCount)})`,
      ])
    );

    renderList(
      document.getElementById("status-list"),
      Object.entries(payload.status_counts || {}).map(([key, count]) => [
        key,
        `${count} (${pct(count, validCount)})`,
      ])
    );

    renderList(
      document.getElementById("country-list"),
      Object.entries(payload.country_counts || {}).map(([key, count]) => [
        key,
        `${count} (${pct(count, validCount)})`,
      ])
    );

    const satisfaction = payload.satisfaction || {};
    const average =
      satisfaction.average === null || satisfaction.average === undefined
        ? "n/a"
        : Number(satisfaction.average).toFixed(2);
    const satisfactionSummary = document.getElementById("satisfaction-summary");
    if (satisfactionSummary) {
      satisfactionSummary.textContent =
        `Scored cases: ${satisfaction.scored_cases ?? 0} of ` +
        `${satisfaction.closed_cases ?? 0}. Average score: ${average} / 5.00`;
    }

    const scoreCounts = satisfaction.score_counts || {};
    renderList(
      document.getElementById("satisfaction-list"),
      [1, 2, 3, 4, 5].map((score) => [
        `Score ${score} (${SCORE_LABELS[score]})`,
        scoreCounts[String(score)] ?? scoreCounts[score] ?? 0,
      ])
    );

    results.classList.remove("is-hidden");
    exportBtn.disabled = false;
  };

  const analyzeFile = async () => {
    const file = selectedFile || fileInput.files?.[0];
    if (!file) {
      setStatus("Choose a CSV file before analyzing.", "is-error");
      showRecovery("analyze");
      return;
    }

    hideRecovery();
    analyzeBtn.disabled = true;
    setStatus("Analyzing…");

    const body = new FormData();
    body.append("file", file, file.name);

    try {
      let response;
      try {
        response = await fetch(`${API_BASE}/api/incidents/analyze`, {
          method: "POST",
          body,
        });
      } catch {
        throw { response: null };
      }

      if (!response.ok) {
        throw { response };
      }

      const payload = await response.json().catch(() => ({}));
      renderResults(payload);
      setStatus(
        (payload.invalid_count ?? 0) > 0
          ? `Analysis complete. ${payload.invalid_count} invalid record(s) found.`
          : "Analysis complete. No invalid records.",
        "is-ok"
      );
    } catch (failure) {
      results.classList.add("is-hidden");
      exportBtn.disabled = true;
      setStatus(toUserFacingFetchError(failure?.response), "is-error");
      showRecovery("analyze");
    } finally {
      analyzeBtn.disabled = false;
    }
  };

  const exportResults = async () => {
    hideRecovery();
    exportBtn.disabled = true;
    setStatus("Exporting…");

    try {
      let response;
      try {
        response = await fetch(`${API_BASE}/api/incidents/results/export`);
      } catch {
        throw { response: null };
      }

      if (!response.ok) {
        throw { response };
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "results.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus("Results CSV downloaded.", "is-ok");
    } catch (failure) {
      setStatus(toUserFacingFetchError(failure?.response), "is-error");
      showRecovery("export");
    } finally {
      exportBtn.disabled = results.classList.contains("is-hidden");
    }
  };

  fileInput.addEventListener("change", () => {
    selectedFile = fileInput.files?.[0] || null;
    fileName.textContent = selectedFile ? selectedFile.name : "No file selected";
  });

  ;["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });

  ;["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    selectedFile = file;
    fileName.textContent = file.name;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await analyzeFile();
  });

  exportBtn.addEventListener("click", async () => {
    await exportResults();
  });

  retryBtn.addEventListener("click", async () => {
    if (lastFailedAction === "export") {
      await exportResults();
      return;
    }
    await analyzeFile();
  });
})();
