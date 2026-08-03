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
              <p className="text-xs text-zinc-500 mt-1 font-mono">Effective Date: August 3, 2026</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-zinc-300 leading-relaxed font-sans">
            <p>Welcome to SidekickAI!</p>

            <p>
              These Terms of Service (&quot;Terms&quot;) govern your access to and use of the SidekickAI website and web application located at{' '}
              <a href="https://sidekickai.onrender.com" className="text-indigo-400 hover:underline transition-all">
                https://sidekickai.onrender.com
              </a>{' '}
              (the &quot;Service&quot; or &quot;Platform&quot;).
            </p>

            <p>
              By accessing or using the Service, you agree to be bound by these Terms. If you disagree with any part of the terms, you may not access or use the Service.
            </p>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                1. Description of Service
              </h2>
              <p>
                SidekickAI is an AI-powered executive assistant platform designed to assist users in prioritizing communications, drafting replies, and coordinating schedules across connected systems (including Gmail, Google Calendar, WhatsApp Business, and LinkedIn).
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                2. Account Registration &amp; Security
              </h2>
              <p>To use the Service, you must create a user profile. You agree to:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li>Provide accurate, current, and complete registration information.</li>
                <li>Maintain the confidentiality of your password and account credentials.</li>
                <li>Accept responsibility for all actions that occur under your account session.</li>
                <li>Immediately notify us of any unauthorized use or security breaches by contacting <a href="mailto:humammoin09@gmail.com" className="text-indigo-400 hover:underline transition-all font-semibold">humammoin09@gmail.com</a>.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                3. Third-Party Integrations &amp; Scope Boundaries
              </h2>
              <p>SidekickAI utilizes API access to sync and write data on your behalf. By authorizing integrations, you acknowledge their specific functional scopes:</p>
              <ul className="list-disc list-inside pl-4 space-y-2 text-zinc-400">
                <li><strong>Google OAuth:</strong> SidekickAI is granted read/write permissions for Gmail messages and Calendar schedules to generate briefs, categorize priorities, and draft or send email replies.</li>
                <li><strong>Meta WhatsApp Cloud API:</strong> Serves only registered business accounts (WABA). Connection requires a business phone number; personal accounts cannot be linked.</li>
                <li><strong>LinkedIn Profile Sync:</strong> Restricted solely to profile metadata sync and post sharing (<code>w_member_social</code>). The Service cannot read or sync LinkedIn private DMs.</li>
              </ul>
              <p>
                We are not liable for any service interruptions, API deprecations, or policy changes implemented by Google, Meta, LinkedIn, or other third-party provider platforms.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                4. User Responsibilities &amp; Acceptable Use
              </h2>
              <p>You agree that you will not use the Service to:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li>Violate any applicable local, state, national, or international laws.</li>
                <li>Distribute unsolicited promotional materials, spam, or bulk marketing messages.</li>
                <li>Inject malicious code, trojans, worms, or attempt unauthorized entry into the database.</li>
                <li>Impersonate any entity or forge email/message headers.</li>
                <li>Interfere with or disrupt the servers or networks connected to the Service.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                5. Intellectual Property Rights
              </h2>
              <p>
                Unless otherwise stated, SidekickAI and/or its licensors own all intellectual property rights for the design, code, graphics, branding, and workflows on the Platform. All rights are reserved. You are granted a limited, non-exclusive, non-transferable license to access the interface for personal or standard business assistant operations.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                6. Disclaimer of Warranties
              </h2>
              <p>
                The Service is provided on an &quot;AS IS&quot; and &quot;AS AVAILABLE&quot; basis. SidekickAI makes no representations or warranties of any kind, express or implied, as to the operation of the Service, the accuracy of AI-generated email/chat drafts, or the completeness of the briefings.
              </p>
              <p>
                We do not warrant that the Service will function uninterrupted, secure, or available at any specific time or location; that any errors or bugs in the software will be corrected immediately; or that the AI-generated drafts are free of errors. <strong>Users must review all draft replies before approving and sending.</strong>
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                7. Limitation of Liability
              </h2>
              <p>
                To the maximum extent permitted by law, in no event shall SidekickAI, nor its directors, employees, partners, agents, or suppliers, be liable for any indirect, incidental, special, consequential, or punitive damages—including loss of profits, data, goodwill, or other intangible losses—resulting from your access to or use of (or inability to use) the Service; any conduct or content of any third party on the Service; or unauthorized access, use, or alteration of your transmissions or database content.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                8. Suspension &amp; Termination
              </h2>
              <p>
                We reserve the right to suspend or terminate your account and restrict access to the Service at our sole discretion, without prior notice or liability, for any reason, including if you breach these Terms. Upon termination, your right to use the Service will cease immediately, and all linked OAuth connections and data will be erased.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                9. Governing Law
              </h2>
              <p>
                These Terms shall be governed and construed in accordance with the laws of the jurisdiction in which SidekickAI operates, without regard to its conflict of law provisions.
              </p>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                10. Modifications to Terms
              </h2>
              <p>
                We reserve the right to modify or replace these Terms at any time. If a revision is material, we will provide at least 15 days&apos; notice before the new terms take effect. By continuing to access or use the Service after those revisions become effective, you agree to be bound by the updated terms.
              </p>
            </div>

            <div className="space-y-3 border-t border-zinc-900/80 pt-6">
              <h2 className="text-lg font-bold text-zinc-100">
                11. Contact Us
              </h2>
              <p>
                If you have any questions about these Terms, please contact us at &apos;{' '}
                <a href="mailto:humammoin09@gmail.com" className="text-indigo-400 hover:underline transition-all font-semibold">
                  humammoin09@gmail.com
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
