import Image from "next/image";
import { siteImages } from "@/lib/assets";

export function ServicesSection() {
  return (
    <section id="services" className="hc-container scroll-mt-32 py-16 lg:py-20 xl:py-24">
      <div className="overflow-hidden rounded-4xl border border-slate-200 bg-white shadow-[0_24px_60px_-32px_rgba(14,58,93,0.35)]">
        <div className="relative overflow-hidden px-8 py-10 sm:px-10 lg:px-12 lg:py-12">
          <Image
            src={siteImages.servicesHealthcare}
            alt="Healthcare technology workspace representing HealthCore outpatient services"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(223,247,242,0.82)_0%,rgba(255,255,255,0.94)_72%)]" />
          <div className="relative">
            <h2 className="text-3xl font-bold text-[#0E3A5D] sm:text-4xl lg:text-[2.75rem]">
              Outpatient Services Built Around Continuity of Care
            </h2>
            <p className="mt-4 max-w-4xl text-lg leading-relaxed text-slate-700 lg:text-xl">
              HealthCore brings together core outpatient services with the scheduling, follow-up, and
              care coordination patients need to move through care with greater confidence.
            </p>
          </div>
        </div>
        <div className="px-8 pb-10 sm:px-10 lg:px-12 lg:pb-12">
          <div className="mt-2 grid gap-6 md:grid-cols-2 xl:grid-cols-4 xl:gap-8">
            <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8">
              <h3 className="text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Primary Care</h3>
              <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
                Primary care designed to support timely appointments, routine needs, and ongoing
                health concerns across the network.
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8">
              <h3 className="text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Specialist Consultations</h3>
              <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
                Specialist consultations delivered within an outpatient model that supports clear
                next steps and coordinated follow-up.
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8">
              <h3 className="text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Chronic Disease Management</h3>
              <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
                Structured support for long-term conditions, helping patients stay connected to care
                across visits and locations.
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8">
              <h3 className="text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Preventive Health Programmes</h3>
              <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
                Preventive health programmes focused on earlier action, regular follow-up, and better
                long-term health planning.
              </p>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
