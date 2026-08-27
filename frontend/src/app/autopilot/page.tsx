'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { 
  Bot, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Sparkles, 
  ArrowRight,
  ShieldCheck,
  Loader2,
  Check,
  MessageSquare,
  Globe,
  Radio,
  Sliders,
  ExternalLink,
  Power,
  Zap,
  Activity,
  CheckSquare
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

export default function AutoPilotPage() {
  const queryClient = useQueryClient();
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

  // Fetch Auto Pilot status & dashboard summary
  const { data: summary, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['autopilot-status-full'],
    queryFn: async () => {
      const response = await apiClient.get('/autopilot/status');
      return response.data;
    },
    refetchInterval: 15000,
  });

  // Toggle ON/OFF Mutation
  const toggleMutation = useMutation({
    mutationFn: async (is_enabled: boolean) => {
      const response = await apiClient.post('/autopilot/toggle', { is_enabled });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['autopilot-status-full'] });
      queryClient.invalidateQueries({ queryKey: ['autopilot-dashboard-summary'] });
    },
  });

  // Trigger Manual Background Check Mutation
  const triggerRunMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/autopilot/trigger-run');
      return response.data;
    },
    onSuccess: (data) => {
      setTriggerMessage(`Background check executed. Processed ${data.cycle_result?.processed_count || 0} items.`);
      queryClient.invalidateQueries({ queryKey: ['autopilot-status-full'] });
      queryClient.invalidateQueries({ queryKey: ['autopilot-dashboard-summary'] });
      setTimeout(() => setTriggerMessage(null), 4000);
    },
    onError: (err: any) => {
      setTriggerMessage(`Background check failed: ${err.message}`);
      setTimeout(() => setTriggerMessage(null), 4500);
    }
  });

  const isEnabled = summary?.is_enabled ?? true;
  const status = summary?.status || 'active';
  const monitoredSources = summary?.monitored_sources || [];
  const activeSourcesCount = summary?.active_sources_count || 0;
  const pendingReviewItems = summary?.pending_review_items || [];
  const recentActivities = summary?.recent_activities || [];

  return (
    <SidebarLayout>
      <div className="p-4 sm:p-6 md:p-8 space-y-8 max-w-7xl mx-auto h-full overflow-y-auto select-none relative">
        
        {/* Header & Main Toggle Control */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900/80 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest uppercase px-2.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-semibold flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" />
                Background Assistance Engine
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-50 mt-1.5">
              Auto Pilot Operations Hub
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
              SidekickAI continuously monitors your connected communications, classifies incoming messages, generates smart drafts, and extracts long-term memory.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => triggerRunMutation.mutate()}
              disabled={triggerRunMutation.isPending || isRefetching || !isEnabled}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-850 text-zinc-200 border border-zinc-800 transition-all cursor-pointer disabled:opacity-50"
            >
              {triggerRunMutation.isPending || isRefetching ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                  Checking sources...
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-indigo-400" />
                  Run Check Now
                </>
              )}
            </button>

            {/* Primary ON / OFF Toggle Switch */}
            <button
              onClick={() => toggleMutation.mutate(!isEnabled)}
              disabled={toggleMutation.isPending}
              className={`flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-xs font-extrabold shadow-lg transition-all cursor-pointer border ${
                isEnabled
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-500/30 shadow-emerald-600/20'
                  : 'bg-zinc-900 hover:bg-zinc-850 text-zinc-400 border-zinc-800'
              }`}
            >
              <Power className={`w-4 h-4 ${isEnabled ? 'text-white' : 'text-zinc-500'}`} />
              {toggleMutation.isPending ? 'Updating...' : isEnabled ? 'AUTO PILOT ON' : 'AUTO PILOT OFF'}
            </button>
          </div>
        </div>

        {triggerMessage && (
          <div className="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-300">
            {triggerMessage}
          </div>
        )}

        {/* Status Card Banner */}
        <div className={`glass-panel p-6 rounded-2xl border-l-4 relative overflow-hidden transition-all ${
          status === 'waiting_for_connection' ? 'border-l-zinc-600 border-zinc-850' :
          status === 'paused' ? 'border-l-amber-500 border-amber-500/20' :
          status === 'error' ? 'border-l-rose-500 border-rose-500/20' : 'border-l-emerald-500 border-emerald-500/20'
        }`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className={`p-2.5 rounded-xl ${
                status === 'active' ? 'bg-emerald-500/10 text-emerald-400' :
                status === 'paused' ? 'bg-amber-500/10 text-amber-400' : 'bg-zinc-800 text-zinc-400'
              }`}>
                <Zap className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-zinc-100 uppercase tracking-wider">
                    Auto Pilot Status: {status.replace('_', ' ').toUpperCase()}
                  </h3>
                  {status === 'active' && (
                    <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  )}
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {status === 'active'
                    ? 'SidekickAI is monitoring your connected applications and handling supported tasks automatically.'
                    : status === 'waiting_for_connection'
                    ? 'No connected applications available for Auto Pilot. Connect an integration to begin background monitoring.'
                    : status === 'paused'
                    ? 'Auto Pilot is currently disabled. Toggle ON to resume background monitoring.'
                    : 'Auto Pilot encountered a temporary error. Background monitoring will retry automatically.'}
                </p>
              </div>
            </div>

            {summary?.last_run_at && (
              <div className="text-right shrink-0">
                <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-550">Last Background Check</span>
                <p className="text-xs font-mono text-zinc-300 mt-0.5">
                  {new Date(summary.last_run_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Connected Sources Grid */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Radio className="w-4 h-4 text-indigo-400" />
              Monitored Integrations ({activeSourcesCount} Active)
            </h3>
            <Link href="/settings" className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline">
              Manage Integrations →
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {monitoredSources.map((src: any) => (
              <div 
                key={src.id}
                className={`glass-panel p-4 rounded-xl space-y-2 border transition-all ${
                  src.is_connected ? 'border-zinc-800 hover:border-indigo-500/30' : 'border-zinc-900/60 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-200">{src.name}</span>
                  <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded border font-semibold ${
                    src.is_connected
                      ? 'bg-emerald-950/30 text-emerald-400 border-emerald-900/30'
                      : 'bg-zinc-900 text-zinc-500 border-zinc-800'
                  }`}>
                    {src.status}
                  </span>
                </div>
                <p className="text-[11px] text-zinc-500">
                  {src.is_connected ? 'Automated monitoring enabled' : 'Not connected'}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Today's Activity Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="glass-panel p-4 rounded-xl space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Items Processed</span>
            <p className="text-2xl font-extrabold text-zinc-100 font-mono">{summary?.processed_today_count || 0}</p>
          </div>
          <div className="glass-panel p-4 rounded-xl space-y-1 border-l-2 border-indigo-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400">Actions Completed</span>
            <p className="text-2xl font-extrabold text-indigo-300 font-mono">{summary?.actions_taken_count || 0}</p>
          </div>
          <div className="glass-panel p-4 rounded-xl space-y-1 border-l-2 border-emerald-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold">Reply Drafts</span>
            <p className="text-2xl font-extrabold text-emerald-300 font-mono">{summary?.actions_taken_count || 0}</p>
          </div>
          <div className="glass-panel p-4 rounded-xl space-y-1 border-l-2 border-amber-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold">Needs Attention</span>
            <p className="text-2xl font-extrabold text-amber-300 font-mono">{summary?.pending_review_count || 0}</p>
          </div>
        </div>

        {/* Needs Your Attention Section (Proactive Action Queue Integration) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-900/80 pb-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Needs Your Attention ({pendingReviewItems.length})
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">Actions requiring executive review before dispatch</span>
          </div>

          {pendingReviewItems.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {pendingReviewItems.map((item: any) => (
                <div key={item.id} className="glass-panel p-5 rounded-xl space-y-3 border-l-2 border-l-amber-500">
                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500">
                    <span className="uppercase px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">{item.source}</span>
                    <span>Received: {item.received_at ? new Date(item.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-zinc-100">{item.sender}</h4>
                    <p className="text-xs text-zinc-300 font-semibold mt-0.5">{item.subject || '(no subject)'}</p>
                    {item.suggested_reply && (
                      <p className="text-[11px] text-zinc-400 mt-2 bg-zinc-900/60 p-2.5 rounded border border-zinc-800/60 font-sans italic line-clamp-2">
                        "{item.suggested_reply}"
                      </p>
                    )}
                  </div>

                  <div className="pt-2 border-t border-zinc-900/60 flex justify-end">
                    <Link
                      href={`/inbox?id=${item.id}`}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md transition-all"
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      Review Draft
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-panel p-10 rounded-xl text-center border border-dashed border-zinc-800 space-y-1">
              <CheckCircle2 className="w-7 h-7 text-emerald-400 mx-auto" />
              <p className="text-xs font-semibold text-zinc-200">No items require manual attention right now.</p>
              <p className="text-[11px] text-zinc-500">Auto Pilot has processed all incoming items according to your policies.</p>
            </div>
          )}
        </div>

        {/* Traceable Recent Auto Pilot Activity Log */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2 border-b border-zinc-900/80 pb-3">
            <Activity className="w-4 h-4 text-indigo-400" />
            Recent Auto Pilot Activity Log
          </h3>

          {recentActivities.length > 0 ? (
            <div className="glass-panel rounded-xl p-5 space-y-3">
              {recentActivities.map((act: any) => (
                <div key={act.id} className="flex items-start justify-between gap-4 p-3 rounded-lg bg-zinc-900/30 border border-zinc-850/60 text-xs">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded border font-semibold ${
                        act.status === 'auto_executed' ? 'bg-emerald-950/30 text-emerald-400 border-emerald-900/30' :
                        act.status === 'pending_user_review' ? 'bg-amber-950/30 text-amber-400 border-amber-900/30' :
                        'bg-zinc-900 text-zinc-400 border-zinc-800'
                      }`}>
                        {act.status.replace('_', ' ')}
                      </span>
                      <span className="font-semibold text-zinc-200 truncate">{act.title}</span>
                    </div>
                    {act.description && (
                      <p className="text-zinc-400 text-[11px] truncate">{act.description}</p>
                    )}
                  </div>

                  <div className="text-right shrink-0 space-y-0.5">
                    <span className="text-[10px] font-mono text-indigo-400 font-semibold">{act.confidence_score}% confidence</span>
                    <p className="text-[10px] font-mono text-zinc-550">
                      {act.created_at ? new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-panel p-10 rounded-xl text-center text-xs text-zinc-550 italic border border-dashed border-zinc-800">
              No recent Auto Pilot activity recorded yet. Activity will populate as background monitoring runs.
            </div>
          )}
        </div>

      </div>
    </SidebarLayout>
  );
}
