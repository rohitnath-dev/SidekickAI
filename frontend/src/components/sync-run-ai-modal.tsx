'use client';

import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  RefreshCw, 
  X, 
  ShieldAlert, 
  ArrowRight,
  Database,
  Sliders,
  Check
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface SyncRunAIModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function SyncRunAIModal({ isOpen, onClose, onSuccess }: SyncRunAIModalProps) {
  const queryClient = useQueryClient();
  const [jobTriggered, setJobTriggered] = useState(false);

  // Poll current job status
  const { data: jobStatus, isLoading: isJobLoading, refetch: refetchJobStatus } = useQuery({
    queryKey: ['ai-job-status-modal'],
    queryFn: async () => {
      const response = await apiClient.get('/ai/job/status');
      return response.data;
    },
    enabled: isOpen,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !data.has_job) return 2000;
      const state = data.state;
      if (state === 'completed' || state === 'failed' || state === 'cancelled' || state === 'stale') {
        return false; // Stop polling when job is in terminal state
      }
      return 1500; // Poll every 1.5s while job is active
    },
  });

  // Fetch connected integration preferences
  const { data: preferences } = useQuery({
    queryKey: ['preferences-modal'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/preferences');
      return response.data;
    },
    enabled: isOpen,
  });

  const connectedServices = preferences?.connected_services || [];
  const hasConnectedApps = connectedServices.some((s: any) => s.connected);

  // Start AI Job Mutation
  const startJobMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/ai/job/start');
      return response.data;
    },
    onSuccess: () => {
      setJobTriggered(true);
      refetchJobStatus();
    },
  });

  // Retry AI Job Mutation
  const retryJobMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/ai/job/retry', {});
      return response.data;
    },
    onSuccess: () => {
      setJobTriggered(true);
      refetchJobStatus();
    },
  });

  // Auto-trigger job when modal opens if no active job exists and user has connected apps
  useEffect(() => {
    if (isOpen && !isJobLoading && jobStatus) {
      if (!jobStatus.has_job && hasConnectedApps && !jobTriggered && !startJobMutation.isPending) {
        startJobMutation.mutate();
      }
    }
  }, [isOpen, isJobLoading, jobStatus, hasConnectedApps, jobTriggered]);

  // Handle completion effects
  useEffect(() => {
    if (jobStatus?.state === 'completed') {
      const formattedTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem('last_synced_at', formattedTime);
        } catch (e) {
          console.warn('Failed to store last_synced_at:', e);
        }
      }

      // Invalidate relevant React Query caches
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      queryClient.invalidateQueries({ queryKey: ['briefing'] });
      queryClient.invalidateQueries({ queryKey: ['planner-briefing'] });
      queryClient.invalidateQueries({ queryKey: ['preferences'] });

      if (onSuccess) {
        onSuccess();
      }
    }
  }, [jobStatus?.state, queryClient, onSuccess]);

  if (!isOpen) return null;

  const state = jobStatus?.state;
  const isCompleted = state === 'completed';
  const isFailed = state === 'failed';
  const isStale = state === 'stale';
  const isActive = ['starting', 'checking_connections', 'syncing', 'processing', 'finalizing'].includes(state);

  const stageName = jobStatus?.state || 'INITIALIZING';
  const itemsDiscovered = jobStatus?.total_items_discovered || 0;
  const itemsProcessed = jobStatus?.items_processed || 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-zinc-950/80 backdrop-blur-xl animate-in fade-in duration-200 select-none">
      
      {/* Background Ambient Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[30rem] h-[30rem] rounded-full bg-indigo-500/10 blur-[120px] pointer-events-none"></div>

      {/* Modal Container */}
      <div className="relative w-full max-w-2xl bg-zinc-950 border border-zinc-850 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-900 bg-zinc-950/60 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Sparkles className="w-4 h-4 animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-zinc-100 tracking-tight">Sidekick AI Operations</h2>
              <p className="text-[11px] text-zinc-450">Data synchronization & executive intelligence pipeline</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          {/* CASE 1: Zero Connected Applications */}
          {!hasConnectedApps && !isActive && !isCompleted ? (
            <div className="py-8 flex flex-col items-center justify-center text-center space-y-4">
              <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-850 text-zinc-400">
                <Database className="w-8 h-8 text-zinc-500" />
              </div>
              <div className="space-y-1.5 max-w-md">
                <h3 className="text-sm font-semibold text-zinc-200">No connected services found</h3>
                <p className="text-xs text-zinc-450 leading-relaxed">
                  Connect Google (Gmail), Slack, Telegram, or Twitter in Settings to give SidekickAI communications data to analyze.
                </p>
              </div>
              <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
                <Link
                  href="/settings"
                  onClick={onClose}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2 cursor-pointer"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  Connect Applications
                </Link>
                <button
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-300 text-xs font-semibold border border-zinc-800 transition-all cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          ) : (

            /* CASE 2: Active / Completed / Failed Job Pipeline */
            <div className="space-y-6">
              
              {/* Stage Progress Card */}
              <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-850 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {isCompleted ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    ) : isFailed || isStale ? (
                      <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
                    ) : (
                      <Loader2 className="w-5 h-5 text-indigo-400 animate-spin shrink-0" />
                    )}
                    <div>
                      <p className="text-xs font-semibold text-zinc-200">
                        {jobStatus?.current_stage || 'Initializing processing pipeline...'}
                      </p>
                      <p className="text-[10px] font-mono text-zinc-500">
                        STAGE: {stageName.toUpperCase()}
                      </p>
                    </div>
                  </div>

                  {itemsDiscovered > 0 && (
                    <span className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-indigo-950/40 text-indigo-300 border border-indigo-900/40">
                      {itemsProcessed} / {itemsDiscovered} Communications
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Steps Checklist */}
              <div className="space-y-2.5 p-4 rounded-xl bg-zinc-950/60 border border-zinc-900">
                <p className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold mb-2">
                  Pipeline Execution Steps
                </p>

                {/* Step 1: Connections */}
                <div className="flex items-center gap-3 text-xs">
                  {['checking_connections', 'syncing', 'processing', 'finalizing', 'completed'].includes(stageName) ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-zinc-700 flex items-center justify-center shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
                    </div>
                  )}
                  <span className={['checking_connections', 'syncing', 'processing', 'finalizing', 'completed'].includes(stageName) ? 'text-zinc-200 font-medium' : 'text-zinc-500'}>
                    Check connected applications & permissions
                  </span>
                </div>

                {/* Step 2: Data Sync */}
                <div className="flex items-center gap-3 text-xs">
                  {['syncing', 'processing', 'finalizing', 'completed'].includes(stageName) ? (
                    stageName === 'syncing' ? (
                      <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    )
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-zinc-700 flex items-center justify-center shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
                    </div>
                  )}
                  <span className={['syncing', 'processing', 'finalizing', 'completed'].includes(stageName) ? 'text-zinc-200 font-medium' : 'text-zinc-500'}>
                    Sync 24-hour communications from connected services
                  </span>
                </div>

                {/* Step 3: AI Processing */}
                <div className="flex items-center gap-3 text-xs">
                  {['processing', 'finalizing', 'completed'].includes(stageName) ? (
                    stageName === 'processing' ? (
                      <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    )
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-zinc-700 flex items-center justify-center shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
                    </div>
                  )}
                  <span className={['processing', 'finalizing', 'completed'].includes(stageName) ? 'text-zinc-200 font-medium' : 'text-zinc-500'}>
                    Analyze messages & extract executive priorities
                  </span>
                </div>

                {/* Step 4: Daily Briefing */}
                <div className="flex items-center gap-3 text-xs">
                  {isCompleted ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : stageName === 'finalizing' ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-zinc-700 flex items-center justify-center shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
                    </div>
                  )}
                  <span className={isCompleted || stageName === 'finalizing' ? 'text-zinc-200 font-medium' : 'text-zinc-500'}>
                    Synthesize daily executive intelligence briefing
                  </span>
                </div>
              </div>

              {/* Per-Integration Sync Status */}
              {jobStatus?.connected_integrations && jobStatus.connected_integrations.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                    Connected Integrations Status
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {jobStatus.connected_integrations.map((item: any) => (
                      <div key={item.provider} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/30 border border-zinc-850 text-xs">
                        <span className="font-medium text-zinc-300">{item.name}</span>
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          {item.status === 'synced' && (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Synced ({item.synced})
                            </span>
                          )}
                          {item.status === 'syncing' && (
                            <span className="text-indigo-400 flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin" /> Syncing...
                            </span>
                          )}
                          {item.status === 'failed' && (
                            <span className="text-rose-400 flex items-center gap-1">
                              <AlertCircle className="w-3 h-3" /> Error
                            </span>
                          )}
                          {item.status === 'pending' && (
                            <span className="text-zinc-500">Pending</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Success Metrics Box */}
              {isCompleted && (
                <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-900/40 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                    <Check className="w-4 h-4 text-emerald-400" />
                    Sync & AI Analysis Complete
                  </div>
                  <div className="text-xs text-zinc-300 space-y-1 font-mono text-[11px]">
                    <p>• Data synced across connected platforms</p>
                    <p>• {itemsProcessed || itemsDiscovered} recent communications analyzed</p>
                    <p>• Executive briefing & proactive queues updated</p>
                  </div>
                </div>
              )}

              {/* Error Box if Failed */}
              {(isFailed || isStale) && (
                <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 space-y-2">
                  <div className="flex items-center gap-2 font-semibold text-rose-200">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    AI Processing Issue Encountered
                  </div>
                  <p className="leading-relaxed text-zinc-300">
                    {jobStatus?.errors?.[0] || 'The system was unable to finish processing your connected data. Please verify your LLM settings.'}
                  </p>
                </div>
              )}

            </div>
          )}

        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-zinc-900 bg-zinc-950/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-[11px] text-zinc-500 font-mono">
            {isActive ? 'Processing 24-hour communications window...' : isCompleted ? 'Executive intelligence ready.' : ''}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            {(isFailed || isStale) && (
              <button
                onClick={() => retryJobMutation.mutate()}
                disabled={retryJobMutation.isPending}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-zinc-900 hover:bg-zinc-850 text-zinc-200 text-xs font-semibold rounded-xl border border-zinc-800 transition-all cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${retryJobMutation.isPending ? 'animate-spin' : ''}`} />
                Try Again
              </button>
            )}

            <button
              onClick={onClose}
              className={`w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                isCompleted 
                  ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20' 
                  : 'bg-zinc-900 hover:bg-zinc-850 text-zinc-300 border border-zinc-800'
              }`}
            >
              {isCompleted ? 'View Dashboard' : 'Close'}
              {isCompleted && <ArrowRight className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
