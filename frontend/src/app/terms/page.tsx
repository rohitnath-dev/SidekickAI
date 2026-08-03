'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, FileText } from 'lucide-react';
import Logo from '@/components/logo';

export default function TermsPage() {
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
              <FileText className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-zinc-100">Terms of Service</h1>
              <p className="text-xs text-zinc-500 mt-1 font-mono">Effective Date: August 2, 2026</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-zinc-300 leading-relaxed font-sans">
            <p>Welcome to SidekickAI!</p>

            <p>
              These terms and conditions outline the rules and regulations for the use of SidekickAI's Website, located at{' '}
              <a href="https://sidekickai.onrender.com" className="text-indigo-400 hover:underline transition-all">
                https://sidekickai.onrender.com
              </a>
              .
            </p>

            <p>
              By accessing this website we assume you accept these terms and conditions. Do not continue to use SidekickAI if you do not agree to all of the terms and conditions stated on this page.
            </p>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                License
              </h2>
              <p>
                Unless otherwise stated, SidekickAI and/or its licensors own the intellectual property rights for all material on SidekickAI. All intellectual property rights are reserved.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                User Responsibilities
              </h2>
              <p>
                You agree to use the application only for lawful purposes and in a way that does not infringe the rights of, restrict, or inhibit anyone else's use and enjoyment of the platform.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                Limitation of Liability
              </h2>
              <p>
                In no event shall SidekickAI, nor any of its officers, directors, and employees, be held liable for anything arising out of or in any way connected with your use of this website.
              </p>
            </div>

            <div className="space-y-3 border-t border-zinc-900/80 pt-6">
              <h2 className="text-lg font-bold text-zinc-100">
                Contact Us
              </h2>
              <p>
                If you have any questions about these Terms, please contact us at{' '}
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
