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
              <p className="text-xs text-zinc-500 mt-1 font-mono">Effective Date: August 3, 2026</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-zinc-300 leading-relaxed font-sans">
            <p>
              SidekickAI (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our web application located at{' '}
              <a href="https://sidekickai.onrender.com" className="text-indigo-400 hover:underline transition-all">
                https://sidekickai.onrender.com
              </a>{' '}
              (the &quot;Service&quot;).
            </p>

            <p>
              By accessing or using our Service, you agree to the collection and use of information in accordance with this Privacy Policy. If you do not agree with any terms of this policy, please do not use the Service.
            </p>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                1. Information Collection
              </h2>
              <p>We collect several types of information to provide and improve our Service:</p>
              
              <h3 className="text-sm font-semibold text-zinc-200 mt-2">A. Information You Provide Directly</h3>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li><strong>Account Information:</strong> When you register for an account, we collect your full name, email address, password (stored securely using industry-standard hashing algorithms), and user preferences.</li>
                <li><strong>Communications:</strong> If you contact us directly, we may collect your email address, message contents, and any attachments you send.</li>
              </ul>

              <h3 className="text-sm font-semibold text-zinc-200 mt-3">B. Third-Party Integrations &amp; OAuth Authorized Data</h3>
              <p>To deliver our AI assistant functionalities, SidekickAI connects with external platforms via OAuth protocol. We access only the permissions you explicitly grant during authentication:</p>
              <ul className="list-disc list-inside pl-4 space-y-2 text-zinc-400">
                <li>
                  <strong>Google Workspace APIs (Gmail &amp; Calendar):</strong>
                  <ul className="list-circle list-inside pl-6 space-y-1 text-zinc-450 mt-1">
                    <li><em>Gmail Scopes:</em> We access Gmail messages (read, modify, send, and compose permissions) to pull email history, synthesize summaries, detect priority threads, and generate draft responses.</li>
                    <li><em>Google Calendar Scopes:</em> We access calendar events (read and write permissions) to retrieve your schedule timeline, update calendar entries, and compile your daily executive briefing.</li>
                    <li><em>OAuth Tokens:</em> We receive and securely store encrypted Google refresh and access tokens to synchronize your data in the background.</li>
                  </ul>
                </li>
                <li>
                  <strong>LinkedIn API:</strong>
                  <ul className="list-circle list-inside pl-6 space-y-1 text-zinc-450 mt-1">
                    <li><em>Scopes Used:</em> We request profile information access and post-sharing scopes (<code>w_member_social</code>).</li>
                    <li><em>Access Limitations:</em> The API only allows us to synchronize your profile metadata and share auto-generated professional posts. We do not (and cannot) read LinkedIn messages, direct chats, or private inbox content.</li>
                  </ul>
                </li>
                <li>
                  <strong>WhatsApp Cloud API:</strong>
                  <ul className="list-circle list-inside pl-6 space-y-1 text-zinc-450 mt-1">
                    <li><em>Embedded Signup flow:</em> Integrates strictly with Meta&apos;s official WhatsApp Business Platform. We access your registered WhatsApp Business Account (WABA) ID, connected phone numbers, and customer chats.</li>
                    <li><em>Access Limitations:</em> This integration requires a dedicated business number. It <strong>cannot</strong> connect personal WhatsApp profiles, read personal chats, or sync standard private numbers.</li>
                  </ul>
                </li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                2. How We Use Your Information
              </h2>
              <p>We use the collected information for various purposes, including to:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li>Operate the Service: Sync email lists, calendar schedules, WhatsApp customer chats, and LinkedIn profiles.</li>
                <li>Generate AI Assist Capabilities: Analyze email headers and body texts using LLMs to prioritize threads, draft proposed reply templates, and build your Daily Briefing.</li>
                <li>Improve &amp; Personalize: Track application performance, resolve configuration bugs, and enhance user experience layouts.</li>
                <li>Security &amp; Authentication: Verify user accounts, secure API sessions, and maintain OAuth credential token rotations.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                3. Data Sharing &amp; Disclosure
              </h2>
              <p>We do not sell, trade, or rent your personal information to third parties. We may disclose data under the following circumstances:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li><strong>With Service Providers:</strong> We share content with verified sub-processors (such as LLM endpoint providers like OpenRouter) solely to process your prompts and draft summaries. These providers are bound by strict confidentiality obligations and do not use your data to train their public models.</li>
                <li><strong>Legal Requirements:</strong> If required by law, subpoena, or government regulation, we may disclose information to comply with valid legal processes.</li>
                <li><strong>Business Transfers:</strong> If SidekickAI undergoes a merger, acquisition, or asset sale, your personal information may be transferred. We will notify you before your data becomes subject to a different policy.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                4. Data Security
              </h2>
              <p>We implement robust administrative, technical, and physical security measures to safeguard your credentials and data:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li><strong>Encryption:</strong> All OAuth credentials (tokens) are stored in our database using strong AES-256 encryption. All network communications use secure HTTPS/TLS transport protocols.</li>
                <li><strong>Access Control:</strong> System database sessions are restricted to authenticated service layers. Database engines are isolated from direct external internet access.</li>
                <li><strong>No Cache Retention for LLMs:</strong> When we send email or chat content to LLM endpoints for synthesis, the data is passed securely and is not cached or used for training.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                5. User Rights
              </h2>
              <p>Depending on your jurisdiction (such as under GDPR or CCPA), you may have the following rights regarding your data:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li><strong>Access &amp; Sync:</strong> You can view all linked data and integrations directly on the dashboard.</li>
                <li><strong>Data Rectification:</strong> You can modify your profile details and connection settings at any time in the Settings portal.</li>
                <li><strong>Data Erasure:</strong> You can delete your account or disconnect specific integrations. Disconnecting a service instantly deletes the corresponding OAuth credentials, synced messages, and cached indexes from our database.</li>
                <li><strong>Contact:</strong> To request complete account erasure or export your details, email us at <a href="mailto:humammoin09@gmail.com" className="text-indigo-400 hover:underline transition-all font-semibold">humammoin09@gmail.com</a>.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                6. Cookies &amp; Tracking Technologies
              </h2>
              <p>We use basic HTTP cookies and local storage tokens to manage user sessions and login authentication states:</p>
              <ul className="list-disc list-inside pl-4 space-y-1 text-zinc-400">
                <li><strong>Auth Cookies:</strong> Secure JWT cookie tokens are stored in your browser to maintain your session state.</li>
                <li><strong>Preferences Storage:</strong> Local storage is used to save theme states and interface layouts.</li>
                <li><strong>No Third-Party Ad Trackers:</strong> We do not host third-party advertisement trackers, analytics beacons, or retargeting scripts.</li>
              </ul>
            </div>

            <div className="space-y-3">
              <h2 className="text-lg font-bold text-zinc-100">
                7. Changes to This Privacy Policy
              </h2>
              <p>
                We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the &quot;Effective Date&quot; at the top. We recommend checking this page periodically for updates.
              </p>
            </div>

            <div className="space-y-3 border-t border-zinc-900/80 pt-6">
              <h2 className="text-lg font-bold text-zinc-100">
                8. Contact Us
              </h2>
              <p>
                If you have any questions or suggestions about our Privacy Policy, do not hesitate to contact us at{' '}
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
