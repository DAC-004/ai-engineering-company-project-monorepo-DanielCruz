import type { Metadata } from "next";
import Link from "next/link";
import { CareRequestForm } from "@/components/CareRequestForm";

export const metadata: Metadata = {
  title: "HealthCore Care Request | Outpatient Appointment Application",
  description:
    "Submit a care request for HealthCore outpatient services across US and UK clinics using an accessible application form for appointment preferences and patient details.",
};

const applicationJsonLd = {
  "@context": "https://schema.org",
  "@type": "MedicalWebPage",
  name: "HealthCore Patient Application",
  about: {
    "@type": "MedicalOrganization",
    name: "HealthCore",
    address: {
      "@type": "PostalAddress",
      addressLocality: "Austin TX",
      addressCountry: "United States",
    },
    email: "care@healthcore.com",
    telephone: ["+15125550142", "+442079460958"],
  },
  description:
    "Application and sign-up page for HealthCore outpatient clinic services in the United States and United Kingdom.",
};

const ApplicationPage = () => (
  <>
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(applicationJsonLd) }}
    />
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-hcBlue focus:shadow-lg"
    >
      Skip to main content
    </a>

    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-white/75">
      <nav className="hc-container flex items-center justify-between py-5 lg:py-6" aria-label="Primary navigation">
        <Link href="/" className="text-2xl font-bold tracking-tight text-hcBlue lg:text-[1.75rem]">
          HealthCore
        </Link>
        <Link
          href="/"
          className="rounded-md px-3 py-2 text-base font-medium hover:text-hcTeal focus-visible:outline focus-visible:outline-2 focus-visible:outline-hcBlue"
        >
          Back to Home
        </Link>
      </nav>
    </header>

    <main id="main-content" className="hc-form-shell scroll-mt-32 py-12 lg:py-16">
      <section className="mb-10">
        <h1 className="text-4xl font-extrabold text-hcBlue lg:text-5xl">Request Outpatient Care</h1>
        <p className="mt-4 text-lg leading-relaxed text-slate-700 lg:text-xl">
          Complete this form to request care with a HealthCore clinic in the United States or United
          Kingdom. Please provide the details needed to review your request and contact you about next
          steps.
        </p>
      </section>
      <CareRequestForm />
    </main>

    <footer className="border-t border-slate-200 bg-white">
      <div className="hc-container py-10 lg:py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:gap-10">
          <div>
            <p className="text-base font-semibold text-hcBlue lg:text-lg">HealthCore Patient Access</p>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              Care request form for outpatient clinics in the United States and United Kingdom.
            </p>
          </div>
          <div>
            <p className="text-base font-semibold text-hcBlue lg:text-lg">Contact</p>
            <address className="mt-3 space-y-2 text-base not-italic text-slate-700 lg:text-lg">
              <p>Headquarters: Austin TX, United States</p>
              <p>Network coverage: Texas, Florida, Georgia, London, Manchester</p>
              <p>
                Email:{" "}
                <a
                  href="mailto:care@healthcore.com"
                  className="text-hcTeal underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-hcBlue"
                >
                  care@healthcore.com
                </a>
              </p>
              <p>
                Phone (US):{" "}
                <a
                  href="tel:+15125550142"
                  className="text-hcTeal underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-hcBlue"
                >
                  +1 (512) 555-0142
                </a>
              </p>
              <p>
                Phone (UK):{" "}
                <a
                  href="tel:+442079460958"
                  className="text-hcTeal underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-hcBlue"
                >
                  +44 20 7946 0958
                </a>
              </p>
            </address>
          </div>
        </div>
        <p className="mt-8 border-t border-slate-200 pt-6 text-base text-slate-600 lg:text-lg">
          © 2026 HealthCore.
        </p>
      </div>
    </footer>
  </>
);

export default ApplicationPage;
