import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/providers";
import PwaRegister from "@/components/pwa-register";
import { BRANDING } from "@/config/branding";

export const metadata: Metadata = {
  title: `${BRANDING.name} — Premium AI Executive Assistant`,
  description: BRANDING.description,
  manifest: "/manifest.json",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100 selection:bg-zinc-800 selection:text-zinc-50 font-sans">
        <Providers>
          <PwaRegister />
          {children}
        </Providers>
      </body>
    </html>
  );
}
