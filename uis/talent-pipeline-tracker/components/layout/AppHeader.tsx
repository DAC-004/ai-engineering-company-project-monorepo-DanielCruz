import Link from "next/link";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="app-shell-wide flex flex-col gap-5 px-4 py-5 sm:px-6 md:flex-row md:items-center md:justify-between lg:py-6">
        <div>
          <Link href="/" className="group inline-block">
            <p className="eyebrow">HealthCore People &amp; Talent</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-hc-blue md:text-3xl lg:text-4xl">
              Internal Talent Pipeline
            </h1>
          </Link>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600 md:text-lg">
            Review candidate records, update application status and hiring stage,
            and maintain internal notes for HealthCore&apos;s outpatient care
            network.
          </p>
        </div>
        <Link href="/candidates/new" className="btn-primary shrink-0">
          Register Candidate
        </Link>
      </div>
    </header>
  );
}
