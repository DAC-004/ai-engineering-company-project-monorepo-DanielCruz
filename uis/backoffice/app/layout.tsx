import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthCore Backoffice | Operations Overview",
  description:
    "Internal HealthCore backoffice view showing visible Milestone 2 TypeScript business-logic output."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#f3f7f8] text-[#10232d] antialiased">
        {children}
      </body>
    </html>
  );
}
