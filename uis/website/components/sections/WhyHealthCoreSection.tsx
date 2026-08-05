import Image from "next/image";
import { siteImages } from "@/lib/assets";

export function WhyHealthCoreSection() {
  return (
    <section id="why-healthcore" className="relative scroll-mt-32 overflow-hidden">
      <Image
        src={siteImages.aboutHealthcare}
        alt="Doctor consulting with a patient in a modern HealthCore clinic"
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(223,247,242,0.72)_0%,rgba(248,250,252,0.88)_100%)]" />
      <div className="relative hc-container py-16 lg:py-20 xl:py-24">
        <h2 className="text-3xl font-bold text-[#0E3A5D] sm:text-4xl lg:text-[2.75rem]">
          Why Patients and Families Choose HealthCore
        </h2>
        <p className="mt-4 max-w-4xl text-lg leading-relaxed text-slate-700 lg:text-xl">
          HealthCore was built to reduce delays, simplify access, and support a more consistent
          outpatient experience across every clinic in the network.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-3 lg:gap-8">
          <article className="rounded-2xl bg-white/90 p-6 shadow-sm ring-1 ring-slate-200 backdrop-blur-sm lg:p-8">
            <h3 className="text-lg font-semibold text-[#0E3A5D] lg:text-xl">Reliable access across the network</h3>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              HealthCore serves patients through clinics in both the US and UK, supporting a more
              connected outpatient journey.
            </p>
          </article>
          <article className="rounded-2xl bg-white/90 p-6 shadow-sm ring-1 ring-slate-200 backdrop-blur-sm lg:p-8">
            <h3 className="text-lg font-semibold text-[#0E3A5D] lg:text-xl">Care that is easier to navigate</h3>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              From appointment requests to follow-up communication, HealthCore is focused on making
              outpatient care easier to understand and access.
            </p>
          </article>
          <article className="rounded-2xl bg-white/90 p-6 shadow-sm ring-1 ring-slate-200 backdrop-blur-sm lg:p-8">
            <h3 className="text-lg font-semibold text-[#0E3A5D] lg:text-xl">Respect for privacy and regulated care</h3>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              Patient information is handled within the responsibilities of HIPAA in the US and UK
              GDPR in the UK.
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
