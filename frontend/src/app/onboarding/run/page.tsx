'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Bot, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  ArrowRight, 
  RefreshCw, 
  Inbox, 
  Sparkles,
  ShieldAlert,
  SlidersHorizontal,
  Home
} from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';

export default function DedicatedRunAIPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [jobStarted, setJobStarted] = useState(false);

  // Poll current job status
  const { data: jobStatus, isLoading, refetch } = useQuery({
    queryKey: ['ai-job-status'],
    queryFn: async () => {
      const response = await apiClient.get('/ai/job/status');
      return response.data;
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !data.has_job) return 2000;
      const state = data.state;
      if (state === 'completed' || state === 'failed' || state === 'cancelled' || state === 'stale') {
        return false; // Stop polling when finished
      }
      return 1500; // Poll every 1.5s while active
    },
  });

  // Start Job Mutation
  const startJobMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/ai/job/start');
      return response.data;
    },
    onSuccess: (data) => {
      setJobStarted(true);
      refetch();
    },
  });

  // Retry Job Mutation
  const retryJobMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/ai/job/retry', {});
      return response.data;
    },
    onSuccess: () => {
      setJobStarted(true);
      refetch();
    },
  });

  // Auto-start job on mount if no active job exists
  useEffect(() => {
    if (!isLoading && jobStatus && !jobStatus.has_job && !jobStarted) {
      startJobMutation.mutate();
    }
  }, [isLoading, jobStatus, jobStarted]);

  // Complete onboarding and navigate to dashboard
  const handleFinishAndGoToDashboard = async () => {
    try {
      await apiClient.post('/auth/complete-onboarding');
    } catch (e) {
      console.warn('Failed to mark onboarding completed:', e);
    }
    router.push('/');
  };

  const isCompleted = ['completed', 'dashboard_ready', 'background_processing'].includes(jobStatus?.state);
  const isFailed = jobStatus?.state === 'failed';
  const isStale = jobStatus?.state === 'stale';
  const hasNoIntegrations = jobStatus?.has_job && jobStatus?.has_connected_sources === false;

  return (
    <div className="flex min-h-screen flex-col justify-between bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Tech grid overlay */}
      <div className="tech-grid opacity-30"></div>

      {/* Floating Ambient Light Blobs */}
      <div className="glowing-blob-container">
        <div className="glowing-blob blob-purple animate-blob-1 -top-20 -left-20"></div>
        <div className="glowing-blob blob-blue animate-blob-2 -bottom-40 -right-20"></div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center relative z-10 my-auto">
        <div className="w-full max-w-2xl space-y-8">
          
          {/* Header */}
          <div className="flex flex-col items-center justify-center text-center">
            <Logo size={44} className="mb-2" />
            <h2 className="mt-4 text-2xl md:text-3xl font-bold tracking-tight text-zinc-50">
              {isCompleted ? 'AI Sync & Processing Complete' : 'Sidekick AI Assistant'}
            </h2>
            <p className="mt-2 text-sm text-zinc-400 max-w-md">
              {isCompleted 
                ? 'Your assistant has analyzed your communications and prepared your daily briefing.' 
                : 'Ingesting communications, extracting key memories, and building your smart executive briefing.'}
            </p>
          </div>

          {/* Card Container */}
          <div className="bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 md:p-8 shadow-2xl backdrop-blur-md space-y-6">
            
            {/* Case A: Zero connected applications */}
            {hasNoIntegrations ? (
              <div className="space-y-6 text-center py-4">
                <div className="mx-auto w-12 h-12 rounded-full bg-zinc-950 border border-zinc-850 flex items-center justify-center text-zinc-400">
                  <SlidersHorizontal className="w-6 h-6" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-base font-semibold text-zinc-200">No connected applications yet</h3>
                  <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                    You chose to skip connecting services. Connect Google, Slack, Telegram, or Twitter anytime in Settings to enable automatic message prioritization and daily AI briefings.
                  </p>
                </div>

                <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <button
                    onClick={() => router.push('/onboarding/integrations')}
                    className="w-full sm:w-auto px-5 py-2.5 bg-zinc-900 hover:bg-zinc-850 text-zinc-200 text-xs font-semibold rounded-lg border border-zinc-800 transition-all cursor-pointer"
                  >
                    Connect Applications
                  </button>

                  <button
                    onClick={handleFinishAndGoToDashboard}
                    className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
                  >
                    Continue to Dashboard
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              /* Case B: Active / Completed / Failed Job State */
              <div className="space-y-6">
                
                {/* Stage Indicator Badge */}
                <div className="flex items-center justify-between p-3.5 rounded-lg bg-zinc-950/60 border border-zinc-850">
                  <div className="flex items-center gap-3">
                    {isCompleted ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : isFailed ? (
                      <AlertCircle className="w-5 h-5 text-rose-400" />
                    ) : (
                      <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                    )}
                    <div>
                      <p className="text-xs font-semibold text-zinc-200">
                        {jobStatus?.current_stage || 'Preparing AI worker...'}
                      </p>
                      <p className="text-[11px] text-zinc-500 font-mono">
                        Stage: {jobStatus?.state?.toUpperCase() || 'INITIALIZING'}
                      </p>
                    </div>
                  </div>

                  {jobStatus?.total_items_discovered > 0 && (
                    <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-indigo-950/30 text-indigo-300 border border-indigo-900/40">
                      {jobStatus.items_processed} / {jobStatus.total_items_discovered} Items
                    </span>
                  )}
                </div>

                {/* Per-Integration Sync Status */}
                {jobStatus?.connected_integrations && jobStatus.connected_integrations.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider text-[10px]">
                      Connected Data Sources
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {jobStatus.connected_integrations.map((item: any) => (
                        <div key={item.provider} className="flex items-center justify-between p-3 rounded-lg bg-zinc-950/40 border border-zinc-900">
                          <span className="text-xs font-medium text-zinc-300">{item.name}</span>
                          <div className="flex items-center gap-2">
                            {item.status === 'synced' && (
                              <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" /> Synced ({item.synced})
                              </span>
                            )}
                            {item.status === 'syncing' && (
                              <span className="text-[10px] font-mono text-indigo-400 flex items-center gap-1">
                                <Loader2 className="w-3 h-3 animate-spin" /> Syncing...
                              </span>
                            )}
                            {item.status === 'failed' && (
                              <span className="text-[10px] font-mono text-rose-400 flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" /> Error
                              </span>
                            )}
                            {item.status === 'pending' && (
                              <span className="text-[10px] font-mono text-zinc-500">Pending</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Error Banner if Failed */}
                {isFailed && (
                  <div className="p-4 rounded-lg bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 leading-relaxed space-y-2">
                    <div className="flex items-center gap-2 font-semibold text-rose-200">
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                      Processing Error
                    </div>
                    <p>{jobStatus?.errors?.[0] || 'AI processing encountered an issue.'}</p>
                  </div>
                )}

                {/* Action Controls */}
                <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-zinc-900">
                  {isFailed || isStale ? (
                    <button
                      onClick={() => retryJobMutation.mutate()}
                      disabled={retryJobMutation.isPending}
                      className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 bg-zinc-900 hover:bg-zinc-850 text-zinc-200 text-xs font-semibold rounded-lg border border-zinc-800 transition-all cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${retryJobMutation.isPending ? 'animate-spin' : ''}`} />
                      Retry Sync & AI Run
                    </button>
                  ) : (
                    <div className="text-[11px] text-zinc-500">
                      {!isCompleted && 'Processes 24-hour communications window.'}
                    </div>
                  )}

                  <button
                    onClick={handleFinishAndGoToDashboard}
                    disabled={!isCompleted && !isFailed && !isStale}
                    className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
                  >
                    {isCompleted ? 'View Executive Dashboard' : 'Processing...'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>

              </div>
            )}

          </div>

        </div>
      </div>

      <footer className="w-full text-center text-xs text-zinc-650 border-t border-zinc-900/40 pt-6 mt-8 relative z-10">
        <p>&copy; {new Date().getFullYear()} SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
