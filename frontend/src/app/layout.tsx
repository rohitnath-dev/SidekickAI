import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/providers";
import PwaRegister from "@/components/pwa-register";

export const metadata: Metadata = {
  title: "SidekickAI — Premium AI Executive Assistant",
  description: "An AI-powered executive assistant that prioritises messages, generates smart replies, remembers context, and helps you stay organised.",
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
