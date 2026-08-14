'use client';

import React, { useEffect } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error("Global Error Boundary caught error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 text-center text-zinc-100 font-sans relative">
      <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[25rem] h-[25rem] rounded-full bg-indigo-500/10 blur-[100px]"></div>

      <div className="relative z-10 max-w-md w-full bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 md:p-8 shadow-2xl backdrop-blur-md space-y-6">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-rose-500" />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-100">
            UI Crash Prevented
          </h2>
          <p className="text-zinc-400 text-xs leading-relaxed">
            An unhandled runtime error occurred in a client component.
          </p>
        </div>

        {error && (
          <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-4 text-left font-mono text-[10px] text-zinc-400 overflow-auto max-h-48 whitespace-pre-wrap">
            {error.message || error.toString()}
          </div>
        )}

        <button
          onClick={() => reset()}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-xs font-semibold text-zinc-950 hover:bg-zinc-200 transition-all cursor-pointer shadow-md"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry rendering
        </button>
      </div>
    </div>
  );
}
