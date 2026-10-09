import Link from "next/link";

const workspaceBase =
  process.env.NEXT_PUBLIC_STAFF_WORKSPACE_URL?.replace(/\/$/, "") ??
  "http://localhost:3000";

const supplierWorkspaceUrl = `${workspaceBase}/backoffice/suppliers`;

/**
 * Historical backoffice route. Supplier mutations moved to the authenticated
 * Internal Workspace; this view performs no HealthCore API calls.
 */
export function SupplierDirectory() {
  return (
    <main className="bo-shell py-8">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-(--bo-accent)">
        Procurement · Compliance
      </p>
      <h1 className="mt-2 text-3xl font-bold">Supplier directory relocated</h1>
      <p className="mt-3 max-w-3xl text-(--bo-muted)">
        Registering suppliers and updating rates or status now requires the Internal Workspace
        session. Sign in once there with your HealthCore JWT; this legacy backoffice route no
        longer calls the supplier API.
      </p>
      <p className="mt-6">
        <Link
          href={supplierWorkspaceUrl}
          className="rounded-full bg-(--bo-accent) px-4 py-2 text-sm font-semibold text-white"
        >
          Open supplier directory in Internal Workspace
        </Link>
      </p>
      <p className="mt-4">
        <Link href="/" className="text-sm font-semibold text-(--bo-accent)">
          Back to operations overview
        </Link>
      </p>
    </main>
  );
}
