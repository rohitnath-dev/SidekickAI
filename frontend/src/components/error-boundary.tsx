'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in UI component:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 text-center text-zinc-100 font-sans relative">
          {/* Tech Grid Background */}
          <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[25rem] h-[25rem] rounded-full bg-indigo-500/10 blur-[100px]"></div>

          <div className="relative z-10 max-w-md w-full bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 md:p-8 shadow-2xl backdrop-blur-md space-y-6">
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-rose-500" />
              </div>
              <h2 className="text-xl font-bold tracking-tight text-zinc-100">
                Application Error
              </h2>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Something went wrong in the user interface. Our apologies for the inconvenience.
              </p>
            </div>

            {this.state.error && (
              <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-4 text-left font-mono text-[10px] text-zinc-400 overflow-auto max-h-48 whitespace-pre-wrap">
                {this.state.error.toString()}
              </div>
            )}

            <button
              onClick={() => window.location.reload()}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-xs font-semibold text-zinc-950 hover:bg-zinc-200 transition-all cursor-pointer shadow-md"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
export default ErrorBoundary;
