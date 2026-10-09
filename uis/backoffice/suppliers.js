(() => {
  const DEFAULT_WORKSPACE = "http://localhost:3000";
  const workspaceBase =
    (typeof window !== "undefined" && window.STAFF_WORKSPACE_URL) || DEFAULT_WORKSPACE;
  const target = `${String(workspaceBase).replace(/\/$/, "")}/backoffice/suppliers`;

  const link = document.getElementById("workspace-supplier-link");
  if (link) {
    link.href = target;
    link.textContent = target;
  }

  const status = document.getElementById("relocation-status");
  if (status) {
    status.textContent =
      "This historical page no longer calls the HealthCore supplier API. Use the Internal Workspace link above.";
  }
})();
