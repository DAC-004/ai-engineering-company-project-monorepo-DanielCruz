import { HeroSection } from "@/components/sections/HeroSection";
import { ServicesSection } from "@/components/sections/ServicesSection";
import { WhyHealthCoreSection } from "@/components/sections/WhyHealthCoreSection";
import { ContactSection } from "@/components/sections/ContactSection";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { LandingFooter } from "@/components/layout/LandingFooter";

export default function Home() {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-[#0E3A5D] focus:shadow-lg"
      >
        Skip to main content
      </a>

      <SiteHeader />

      <main id="main-content" className="scroll-mt-32">
        <HeroSection />
        <ServicesSection />
        <WhyHealthCoreSection />
        <ContactSection />
      </main>

      <LandingFooter />
    </>
  );
}
