import { Navbar } from "@/components/landing/Navbar";
import { Hero } from "@/components/landing/Hero";
import { MissionSection } from "@/components/landing/MissionSection";
import { HardwareSection } from "@/components/landing/HardwareSection";
import { CtaSection } from "@/components/landing/CtaSection";
import { Footer } from "@/components/landing/Footer";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground antialiased">
      <Navbar />
      <main>
        <Hero />
        <MissionSection />
        <HardwareSection />
        <CtaSection />
      </main>
      <Footer />
    </div>
  );
}
