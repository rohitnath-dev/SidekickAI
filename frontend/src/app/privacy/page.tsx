'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Shield } from 'lucide-react';
import Logo from '@/components/logo';

export default function PrivacyPage() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100 font-sans relative overflow-hidden select-none">
      {/* Background Grid */}
      <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
      
      {/* Ambient glowing spots */}
      <div className="absolute top-10 left-1/4 w-[30rem] h-[30rem] rounded-full bg-indigo-500/5 blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-10 right-1/4 w-[30rem] h-[30rem] rounded-full bg-purple-500/5 blur-[120px] pointer-events-none"></div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 border-b border-zinc-900/60 bg-zinc-950/60 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <Link href="/" className="inline-block">
          <Logo size={28} />
        </Link>
        <Link 
          href="/login" 
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/40 text-xs font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-700 transition-all cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Login
        </Link>
      </header>

      {/* Content Area */}
      <main className="flex-1 max-w-3xl w-full mx-auto px-6 py-16 relative z-10">
        <div className="glass-panel border border-zinc-900 rounded-2xl p-8 md:p-12 bg-zinc-900/10 backdrop-blur-xl space-y-8 shadow-2xl">
          <div className="flex items-center gap-3 border-b border-zinc-900/80 pb-6">
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Shield className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-zinc-100">Privacy Policy</h1>
              <p className="text-xs text-zinc-500 mt-1 font-mono">Effective Date: August 2, 2026</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-zinc-300 leading-relaxed font-sans">
            <p>
              At SidekickAI, accessible from{' '}
              <a href="https://sidekickai.onrender.com" className="text-indigo-400 hover:underline transition-all">
                https://sidekickai.onrender.com
              </a>
              , one of our main priorities is the privacy of our visitors. This Privacy Policy document contains types of information that is collected and recorded by SidekickAI and how we use it.
            </p>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                Information We Collect
              </h2>
              <p>
                SidekickAI integrates with third-party services like Google, LinkedIn, and WhatsApp to provide AI-driven assistant features. When you authenticate via Google (Gmail) or other platforms, we only access the necessary permissions required to deliver the core functionalities of the application.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                How We Use Your Information
              </h2>
              <p>We use the information we collect in various ways, including to:</p>
              <ul className="list-disc list-inside pl-4 space-y-2 text-zinc-400 font-sans">
                <li>Provide, operate, and maintain our web application.</li>
                <li>Improve, personalize, and expand our application.</li>
                <li>Communicate with you for support and updates.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                Data Security
              </h2>
              <p>
                We value your trust in providing us your information, thus we are striving to use commercially acceptable means of protecting it.
              </p>
            </div>

            <div className="space-y-3 border-t border-zinc-900/80 pt-6">
              <h2 className="text-lg font-bold text-zinc-100">
                Contact Us
              </h2>
              <p>
                If you have any questions or suggestions about our Privacy Policy, do not hesitate to contact us at{' '}
                <a href="mailto:humammoin@gmail.com" className="text-indigo-400 hover:underline transition-all font-semibold">
                  humammoin@gmail.com
                </a>
                .
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 border-t border-zinc-900/60 bg-zinc-950/40 text-center text-xs text-zinc-500 relative z-10">
        <div className="flex justify-center gap-6 mb-3">
          <Link href="/privacy" className="hover:text-zinc-300 transition-colors">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-zinc-300 transition-colors">
            Terms of Service
          </Link>
        </div>
        <p>&copy; 2026 SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
