'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';
import AIConfigForm from '@/components/ai-config-form';

export default function AIOnboardingPage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    let isCancelled = false;
    let timeoutId: any;

    const verifyAuth = async () => {
      try {
        timeoutId = setTimeout(() => {
          if (!isCancelled) {
            console.warn('[Auth Timeout] AI Onboarding auth check took too long, redirecting to login');
            window.location.href = '/login';
          }
        }, 4000); // 4 seconds max wait

        console.log('[AI Onboarding] Verifying session and AI configuration status...');
        const response = await apiClient.get('/auth/me');

        if (!isCancelled) {
          clearTimeout(timeoutId);
          if (response.data && response.data.has_ai_config === true) {
            if (response.data.onboarding_completed === false) {
              console.log('[AI Onboarding] AI provider configured. Proceeding to intermediate Settings step.');
              router.push('/onboarding/settings');
            } else {
              console.log('[AI Onboarding] Onboarding already completed. Redirecting to dashboard.');
              router.push('/');
            }
          } else {
            setCheckingAuth(false);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          clearTimeout(timeoutId);
          console.log('[AI Onboarding] Session verification failed. Redirecting to login.', err);
          window.location.href = '/login';
        }
      }
    };

    verifyAuth();

    return () => {
      isCancelled = true;
      clearTimeout(timeoutId);
    };
  }, [router]);

  if (checkingAuth) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-950 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
        {/* Glowing Ambient Spot */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[25rem] h-[25rem] rounded-full bg-indigo-500/10 blur-[100px] animate-pulse"></div>
        
        <div className="relative z-10 flex flex-col items-center">
          <Logo size={48} className="animate-pulse" />
          <p className="mt-4 text-xs font-mono text-zinc-550 tracking-widest uppercase animate-pulse">Checking credentials...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col justify-between bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Tech grid overlay */}
      <div className="tech-grid opacity-30"></div>

      {/* Futuristic Floating Ambient Light Blobs */}
      <div className="glowing-blob-container">
        <div className="glowing-blob blob-purple animate-blob-1 -top-20 -left-20"></div>
        <div className="glowing-blob blob-blue animate-blob-2 -bottom-40 -right-20"></div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center relative z-10">
        <div className="w-full max-w-2xl space-y-8">
          <div className="flex flex-col items-center justify-center text-center">
            <Logo size={48} className="mb-2" />
            <h2 className="mt-6 text-2xl font-bold tracking-tight text-zinc-50">
              Choose your AI
            </h2>
            <p className="mt-2 text-sm text-zinc-400 max-w-md">
              Choose how Sidekick AI should power your assistant. Select OpenRouter to use hosted cloud endpoints or Ollama to run locally.
            </p>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 md:p-8 shadow-2xl backdrop-blur-md">
            <AIConfigForm onSaveSuccess={() => router.push('/onboarding/settings')} />
          </div>
        </div>
      </div>

      <footer className="w-full text-center text-xs text-zinc-650 border-t border-zinc-900/40 pt-6 mt-8 relative z-10">
        <p>&copy; {new Date().getFullYear()} SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
