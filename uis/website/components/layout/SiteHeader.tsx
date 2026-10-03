import Link from "next/link";

type SiteHeaderProps = {
  homeHref?: string;
  showMenu?: boolean;
};

export function SiteHeader({ homeHref = "/", showMenu = true }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur supports-backdrop-filter:bg-white/75">
      <nav
        className="hc-container flex flex-wrap items-center justify-between gap-4 py-5 lg:py-6"
        aria-label="Primary navigation"
      >
        <Link href={homeHref} className="text-2xl font-bold tracking-tight text-[#0E3A5D] lg:text-[1.75rem]">
          HealthCore
        </Link>

        {showMenu ? (
          <ul className="flex flex-wrap items-center justify-end gap-4 text-base font-medium sm:gap-8 lg:gap-10">
            <li>
              <a
                href="#services"
                className="rounded-md px-3 py-2 hover:text-[#0E7490] focus-visible:outline-2 focus-visible:outline-[#0E3A5D]"
              >
                Services
              </a>
            </li>
            <li>
              <a
                href="#why-healthcore"
                className="rounded-md px-3 py-2 hover:text-[#0E7490] focus-visible:outline-2 focus-visible:outline-[#0E3A5D]"
              >
                Why HealthCore
              </a>
            </li>
            <li>
              <a
                href="#contact"
                className="rounded-md px-3 py-2 hover:text-[#0E7490] focus-visible:outline-2 focus-visible:outline-[#0E3A5D]"
              >
                Contact
              </a>
            </li>
            <li>
              <Link
                href="/application"
                className="rounded-lg bg-[#0E3A5D] px-5 py-2.5 text-base font-semibold text-white shadow-sm hover:bg-[#0E7490] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0E3A5D]"
              >
                Apply
              </Link>
            </li>
          </ul>
        ) : (
          <Link
            href="/"
            className="rounded-md px-3 py-2 text-base font-medium hover:text-[#0E7490] focus-visible:outline-2 focus-visible:outline-[#0E3A5D]"
          >
            Back to Home
          </Link>
        )}
      </nav>
    </header>
  );
}
