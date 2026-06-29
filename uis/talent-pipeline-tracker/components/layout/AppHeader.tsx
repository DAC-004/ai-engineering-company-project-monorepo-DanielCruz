import Link from "next/link";

export function AppHeader() {
  return (
    <header className="border-b border-white/10 bg-slate-950 text-white">
      <div className="app-shell-wide flex flex-col gap-5 px-4 py-6 sm:px-6 md:flex-row md:items-center md:justify-between lg:py-8">
        <div>
          <Link href="/" className="group inline-block">
            <p className="eyebrow">HealthCore Digital · People &amp; Workforce</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-white md:text-4xl">
              Talent Pipeline Tracker
            </h1>
          </Link>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-300 md:text-lg">
            Command center for clinical hiring across 12 HealthCore clinic
            locations — candidate review, pipeline updates, and recruiter notes.
          </p>
        </div>
        <Link href="/candidates/new" className="btn-primary shrink-0">
          Add Candidate
        </Link>
      </div>
    </header>
  );
}
