import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthCore | Trusted Outpatient Care Across the US and UK",
  description:
    "HealthCore is an outpatient care network serving communities across the US and UK with primary care, specialist consultations, chronic disease management, and preventive health programmes."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-[#0F172A] antialiased selection:bg-cyan-100 selection:text-[#0E3A5D]">
        {children}
      </body>
    </html>
  );
}
