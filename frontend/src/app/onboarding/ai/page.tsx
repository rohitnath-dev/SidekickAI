'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';
import AIConfigForm from '@/components/ai-config-form';

export default function AIOnboardingPage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const checkAuth = useCallback(async () => {
    setCheckingAuth(true);
    setAuthError(null);
    try {
      console.log('[AI Onboarding] Verifying session and AI configuration status...');
      const response = await apiClient.get('/auth/me', { timeout: 5000 });
      if (response.data && response.data.has_ai_config === true) {
        console.log('[AI Onboarding] AI provider already configured. Redirecting to dashboard.');
        router.push('/');
      } else {
        setCheckingAuth(false);
      }
    } catch (err: any) {
      console.error('[AI Onboarding] Auth check failed:', err);
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout');
      const isNetworkError = !err.response;

      if (isTimeout || isNetworkError) {
        setAuthError(
          isTimeout
            ? 'Connection timed out. The backend server might be starting up or sleeping.'
            : 'Could not connect to the backend server. Please verify your connection.'
        );
        setCheckingAuth(false);
      } else {
        console.log('[AI Onboarding] Session verification failed. Redirecting to login.');
        router.push('/login');
      }
    }
  }, [router]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (authError) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-950 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
        {/* Glowing Ambient Spot */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[25rem] h-[25rem] rounded-full bg-indigo-500/10 blur-[100px]"></div>
        
        <div className="relative z-10 max-w-sm w-full bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 md:p-8 shadow-2xl backdrop-blur-md space-y-6 text-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-amber-500" />
            </div>
            <h2 className="text-lg font-bold tracking-tight text-zinc-150">
              Connection Issue
            </h2>
            <p className="text-zinc-400 text-xs leading-relaxed">
              {authError}
            </p>
          </div>

          <button
            onClick={checkAuth}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-xs font-semibold text-zinc-950 hover:bg-zinc-200 transition-all cursor-pointer shadow-md"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

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
            <AIConfigForm onSaveSuccess={() => router.push('/')} />
          </div>
        </div>
      </div>

      <footer className="w-full text-center text-xs text-zinc-650 border-t border-zinc-900/40 pt-6 mt-8 relative z-10">
        <p>&copy; {new Date().getFullYear()} SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
