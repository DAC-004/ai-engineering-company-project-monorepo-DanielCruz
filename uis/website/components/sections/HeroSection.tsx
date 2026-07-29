import Image from "next/image";
import Link from "next/link";
import { siteImages } from "@/lib/assets";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden text-white">
      <Image
        src={siteImages.heroHealthcare}
        alt="Modern hospital corridor representing HealthCore outpatient care access"
        className="absolute inset-0 h-full w-full object-cover"
        priority
      />
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(14,58,93,0.84)_0%,rgba(17,94,117,0.8)_52%,rgba(14,116,144,0.78)_100%)]" />
      <div className="absolute inset-0 opacity-20">
        <div className="absolute -left-12 top-10 h-40 w-40 rounded-full bg-cyan-200 blur-3xl" />
        <div className="absolute right-0 top-0 h-56 w-56 translate-x-1/4 -translate-y-1/4 rounded-full bg-white/20 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-40 w-40 rounded-full bg-emerald-200/30 blur-3xl" />
      </div>
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-size-[32px_32px] opacity-10" />

      <div className="relative hc-container grid gap-10 py-20 lg:grid-cols-[1.15fr_0.85fr] lg:gap-14 lg:py-28 xl:py-32">
        <div>
          <p className="mb-4 inline-flex rounded-full border border-white/20 bg-white/12 px-4 py-1.5 text-sm font-semibold uppercase tracking-[0.18em] text-cyan-50">
            Outpatient Care Network | United States and United Kingdom
          </p>
          <h1 className="text-4xl font-extrabold leading-[1.08] sm:text-5xl lg:text-6xl xl:text-[4rem]">
            Outpatient care designed to be clear, timely, and easier to access.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-cyan-50 sm:text-xl lg:max-w-3xl lg:text-2xl">
            Founded in Austin TX in 2011, HealthCore supports patients across 12 clinics in Texas,
            Florida, Georgia, London, and Manchester. Our network provides primary care, specialist
            consultations, chronic disease management, and preventive health programmes with a focus
            on coordinated outpatient care.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              href="/application"
              className="rounded-lg bg-white px-6 py-3.5 text-base font-semibold text-[#0E3A5D] shadow-sm hover:bg-cyan-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white lg:px-8 lg:py-4 lg:text-lg"
            >
              Request Care Access
            </Link>
            <a
              href="#services"
              className="rounded-lg border border-white/60 px-6 py-3.5 text-base font-semibold text-white hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white lg:px-8 lg:py-4 lg:text-lg"
            >
              View Our Services
            </a>
          </div>
        </div>

        <div className="grid gap-5 self-center lg:gap-6">
          <div className="rounded-3xl border border-white/20 bg-white/12 p-7 shadow-2xl shadow-cyan-950/20 backdrop-blur-md lg:p-8">
            <h2 className="text-2xl font-semibold lg:text-[1.75rem]">HealthCore at a glance</h2>
            <ul className="mt-5 space-y-4 text-base leading-relaxed text-cyan-50 lg:text-lg">
              <li><strong>Founded in 2011</strong> to make high-quality outpatient care easier to access</li>
              <li><strong>12 clinics</strong> serving patients across the United States and United Kingdom</li>
              <li><strong>200 team members</strong> across clinical, operational, and administrative roles</li>
              <li><strong>Four core service areas</strong> spanning primary, specialist, chronic, and preventive care</li>
            </ul>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <article className="rounded-2xl border border-white/20 bg-slate-950/15 p-5 backdrop-blur-sm lg:p-6">
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-cyan-100">Patient access</p>
              <p className="mt-3 text-base leading-relaxed text-cyan-50 lg:text-lg">
                Same-day bookings, extended hours, and clear follow-up support in key markets.
              </p>
            </article>
            <article className="rounded-2xl border border-white/20 bg-slate-950/15 p-5 backdrop-blur-sm lg:p-6">
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-cyan-100">Responsible care</p>
              <p className="mt-3 text-base leading-relaxed text-cyan-50 lg:text-lg">
                Healthcare delivery informed by regulated data responsibilities in both the US and UK.
              </p>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
