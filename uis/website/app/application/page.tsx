import type { Metadata } from "next";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { ApplicationFooter } from "@/components/layout/ApplicationFooter";
import { CareRequestForm } from "@/components/forms/CareRequestForm";

export const metadata: Metadata = {
  title: "HealthCore Care Request | Outpatient Appointment Application",
  description:
    "Submit a care request for HealthCore outpatient services across US and UK clinics using an accessible application form for appointment preferences and patient details."
};

export default function ApplicationPage() {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-[#0E3A5D] focus:shadow-lg"
      >
        Skip to main content
      </a>

      <SiteHeader showMenu={false} />

      <main id="main-content" className="hc-form-shell scroll-mt-32 py-12 lg:py-16">
        <section className="mb-10">
          <h1 className="text-4xl font-extrabold text-[#0E3A5D] lg:text-5xl">Request Outpatient Care</h1>
          <p className="mt-4 text-lg leading-relaxed text-slate-700 lg:text-xl">
            Complete this form to request care with a HealthCore clinic in the United States or
            United Kingdom. Please provide the details needed to review your request and contact you
            about next steps.
          </p>
        </section>

        <section className="rounded-2xl bg-white p-7 shadow-sm ring-1 ring-slate-200 sm:p-9 lg:p-10">
          <CareRequestForm />
        </section>
      </main>

      <ApplicationFooter />
    </>
  );
}
