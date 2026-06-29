import Link from "next/link";

export function AppHeader() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <div>
          <Link href="/" className="group inline-block">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">
              HealthCore Digital
            </p>
            <h1 className="text-xl font-semibold text-slate-900 group-hover:text-teal-800">
              Talent Pipeline
            </h1>
          </Link>
          <p className="mt-1 text-sm text-slate-600">
            People &amp; Workforce · Clinical hiring across 12 clinic locations
          </p>
        </div>
        <Link
          href="/candidates/new"
          className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
        >
          Add Candidate
        </Link>
      </div>
    </header>
  );
}
