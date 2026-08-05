import Image from "next/image";
import Link from "next/link";
import { siteImages } from "@/lib/assets";

export function ContactSection() {
  return (
    <section id="contact" className="hc-container scroll-mt-32 py-16 lg:py-20 xl:py-24">
      <div className="relative overflow-hidden rounded-4xl border border-slate-200 bg-white p-8 shadow-[0_24px_60px_-32px_rgba(14,58,93,0.28)] ring-1 ring-slate-200 lg:grid lg:grid-cols-2 lg:gap-10 lg:p-10 xl:p-12">
        <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_center,rgba(14,116,144,0.12),transparent_66%)] lg:block" />
        <div>
          <h2 className="text-3xl font-bold text-[#0E3A5D] sm:text-4xl">Questions About Care Access?</h2>
          <p className="mt-4 text-lg leading-relaxed text-slate-700 lg:text-xl">
            If you are looking for outpatient care or want to learn more about HealthCore services,
            you can submit an application request and our team will review your information.
          </p>
          <dl className="mt-8 space-y-3 text-base text-slate-700 lg:text-lg">
            <div>
              <dt className="font-semibold">Headquarters</dt>
              <dd>Austin TX, United States</dd>
            </div>
            <div>
              <dt className="font-semibold">Network coverage</dt>
              <dd>Texas, Florida, Georgia, London, Manchester</dd>
            </div>
            <div>
              <dt className="font-semibold">Email</dt>
              <dd><a href="mailto:care@healthcore.com" className="text-[#0E7490] underline-offset-2 hover:underline">care@healthcore.com</a></dd>
            </div>
            <div>
              <dt className="font-semibold">Phone (US)</dt>
              <dd><a href="tel:+15125550142" className="text-[#0E7490] underline-offset-2 hover:underline">+1 (512) 555-0142</a></dd>
            </div>
            <div>
              <dt className="font-semibold">Phone (UK)</dt>
              <dd><a href="tel:+442079460958" className="text-[#0E7490] underline-offset-2 hover:underline">+44 20 7946 0958</a></dd>
            </div>
          </dl>
        </div>

        <div className="relative overflow-hidden rounded-2xl p-6 ring-1 ring-slate-200 lg:p-8">
          <Image
            src={siteImages.careTeamHealthcare}
            alt="HealthCore care team collaborating in a modern clinical setting"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.88)_0%,rgba(255,255,255,0.92)_100%)]" />
          <div className="relative">
            <h3 className="text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Begin your care request</h3>
            <p className="mt-3 text-base leading-relaxed text-slate-700 lg:text-lg">
              Share your preferred clinic, service type, and contact details so HealthCore can review
              your request for outpatient care access.
            </p>
            <Link
              href="/application"
              className="mt-6 inline-flex rounded-lg bg-[#0E3A5D] px-6 py-3.5 text-base font-semibold text-white shadow-sm hover:bg-[#0E7490] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0E3A5D] lg:px-8 lg:py-4 lg:text-lg"
            >
              Open the Application Form
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
