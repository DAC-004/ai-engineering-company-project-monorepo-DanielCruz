import Link from "next/link";

export function LandingFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="hc-container py-10 lg:py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3 lg:gap-10">
          <div>
            <p className="text-base font-semibold text-[#0E3A5D] lg:text-lg">HealthCore</p>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              Outpatient care services across the United States and United Kingdom.
            </p>
          </div>
          <div>
            <p className="text-base font-semibold text-[#0E3A5D] lg:text-lg">Contact</p>
            <address className="mt-3 space-y-2 text-base not-italic text-slate-700 lg:text-lg">
              <p>Headquarters: Austin TX, United States</p>
              <p>Network coverage: Texas, Florida, Georgia, London, Manchester</p>
              <p>
                Email: <a className="text-[#0E7490] underline-offset-2 hover:underline" href="mailto:care@healthcore.com">care@healthcore.com</a>
              </p>
              <p>
                Phone (US): <a className="text-[#0E7490] underline-offset-2 hover:underline" href="tel:+15125550142">+1 (512) 555-0142</a>
              </p>
              <p>
                Phone (UK): <a className="text-[#0E7490] underline-offset-2 hover:underline" href="tel:+442079460958">+44 20 7946 0958</a>
              </p>
            </address>
          </div>
          <div>
            <p className="text-base font-semibold text-[#0E3A5D] lg:text-lg">Care access</p>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              Submit a care request online or contact our patient access team for appointment support.
            </p>
            <Link
              href="/application"
              className="mt-4 inline-flex text-base font-semibold text-[#0E7490] underline-offset-2 hover:underline lg:text-lg"
            >
              Open application form
            </Link>
          </div>
        </div>
        <p className="mt-8 border-t border-slate-200 pt-6 text-base text-slate-600 lg:text-lg">
          © 2026 HealthCore. Supporting clearer access, continuity of care, and responsible handling
          of patient information.
        </p>
      </div>
    </footer>
  );
}
