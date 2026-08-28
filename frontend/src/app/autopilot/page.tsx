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
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900/80 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest uppercase px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 font-semibold flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" />
                AUTO PILOT — COMING SOON
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-50 mt-1.5">
              Auto Pilot Operations Hub
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
              Automatic background assistance across your connected applications is coming soon.
            </p>
          </div>
        </div>

        {/* Status Card Banner */}
        <div className="glass-panel p-6 rounded-2xl border-l-4 border-l-indigo-500 border-zinc-850 relative overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400">
                <Zap className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-zinc-100 uppercase tracking-wider">
                    AUTO PILOT — COMING SOON
                  </h3>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed max-w-3xl">
                  SidekickAI will soon provide full autonomous background monitoring across your connected channels. In the upcoming release, Auto Pilot will automatically classify messages, extract memories, prepare smart drafts, and dispatch urgent alerts without requiring manual triggers.
                </p>
              </div>
            </div>
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

        {/* Planned Core Automation Features */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2 border-b border-zinc-900/80 pb-3">
            <Bot className="w-4 h-4 text-indigo-400" />
            Planned Auto Pilot Capabilities
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-panel p-6 rounded-2xl space-y-3 border border-zinc-850">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 w-fit">
                <Radio className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-zinc-100">Continuous Channel Monitoring</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Background workers will automatically poll connected Gmail, Slack, Telegram, and Twitter feeds for unread messages without requiring manual sync triggers.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-2xl space-y-3 border border-zinc-850">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 w-fit">
                <Sparkles className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-zinc-100">Smart Contextual Drafting</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Autonomous draft generation utilizing thread history and long-term user memory context, holding responses in the Proactive Queue for executive review.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-2xl space-y-3 border border-zinc-850">
              <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 w-fit">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-zinc-100">Urgent Escalations</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Automatic detection of critical inquiries, deadlines, and high-priority messages with instant proactive alerts delivered directly to your executive briefing.
              </p>
            </div>
          </div>
        </div>

      </div>
    </SidebarLayout>
  );
}
