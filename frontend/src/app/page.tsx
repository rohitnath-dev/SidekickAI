'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { 
  ArrowRight, 
  Mail, 
  Calendar, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Sparkles, 
  TrendingUp,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  RefreshCw,
  Loader2,
  Check,
  Trash,
  MessageSquare,
  Globe,
  ChevronDown,
  ChevronUp,
  Bot
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';
import SyncRunAIModal from '@/components/sync-run-ai-modal';

const PROVIDER_METADATA: Record<string, { name: string; dotClass: string; containerClass: string }> = {
  google: {
    name: 'Google Workspace',
    dotClass: 'bg-red-500',
    containerClass: 'bg-red-500/20 border-red-500/30'
  },
  twitter: {
    name: 'Twitter / X',
    dotClass: 'bg-zinc-100',
    containerClass: 'bg-zinc-500/20 border-zinc-500/30'
  }
};

export default function DashboardPage() {
  // Fetch user profile info
  const { data: user } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      const response = await apiClient.get('/auth/me');
      return response.data;
    },
  });

  // Fetch daily executive briefing
  const { data: briefing, isLoading: isBriefingLoading, refetch: refetchBriefing } = useQuery({
    queryKey: ['briefing'],
    queryFn: async () => {
      const response = await apiClient.get('/planner/briefing');
      return response.data;
    },
    retry: false, // Don't spam if backend LLM API fails
  });

  const { data: autopilotSummary } = useQuery({
    queryKey: ['autopilot-dashboard-summary'],
    queryFn: async () => {
      const response = await apiClient.get('/autopilot/dashboard-summary');
      return response.data;
    },
    refetchInterval: 15000,
  });

  const queryClient = useQueryClient();

  const [syncLoading, setSyncLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  
  const [aiLoading, setAiLoading] = useState(false);
  const [aiStatus, setAiStatus] = useState<string | null>(null);

  const syncMutation = useMutation({
    mutationFn: async () => {
      setSyncLoading(true);
      setSyncStatus('Syncing...');
      const response = await apiClient.post('/settings/sync');
      return response.data;
    },
    onSuccess: (data) => {
      setSyncStatus(`Sync completed! Synced ${data.synced} items.`);
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
      setTimeout(() => setSyncStatus(null), 4000);
    },
    onError: (err: any) => {
      console.error(err);
      const detail = err.response?.data?.detail || err.message;
      setSyncStatus(`Sync failed: ${detail}`);
      setTimeout(() => setSyncStatus(null), 4500);
    },
    onSettled: () => {
      setSyncLoading(false);
    }
  });

  const runAiMutation = useMutation({
    mutationFn: async () => {
      setAiLoading(true);
      setAiStatus('Running AI...');
      const response = await apiClient.post('/ai/run', {});
      return response.data;
    },
    onSuccess: (data) => {
      setAiStatus(`AI complete! Processed ${data.processed_count} messages.`);
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
      queryClient.invalidateQueries({ queryKey: ['briefing'] });
      setTimeout(() => setAiStatus(null), 4000);
    },
    onError: (err: any) => {
      console.error(err);
      const detail = err.response?.data?.detail || err.message;
      setAiStatus(`AI processing failed: ${detail}`);
      setTimeout(() => setAiStatus(null), 4500);
    },
    onSettled: () => {
      setAiLoading(false);
    }
  });
  const [draftEdits, setDraftEdits] = useState<Record<number, string>>({});
  const [actionStatuses, setActionStatuses] = useState<Record<number, { message: string, isError: boolean } | null>>({});
  const [expandedSummary, setExpandedSummary] = useState<Record<number, boolean>>({});
  const seenMessageIds = React.useRef<Set<number>>(new Set());
  const [notification, setNotification] = useState<{ id: number, sender: string, subject: string } | null>(null);

  // Approve & Send Mutation
  const approveMutation = useMutation({
    mutationFn: async ({ id, replyText }: { id: number, replyText: string }) => {
      const response = await apiClient.post(`/reply/message/${id}/approve`, {
        reply_text: replyText
      });
      return response.data;
    },
    onSuccess: (data, variables) => {
      setActionStatuses(prev => ({
        ...prev,
        [variables.id]: { message: "Reply approved and sent successfully!", isError: false }
      }));
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
      setTimeout(() => {
        setActionStatuses(prev => ({ ...prev, [variables.id]: null }));
      }, 3500);
    },
    onError: (error: any, variables) => {
      console.error(error);
      const detail = error.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : (detail?.message || 'Failed to dispatch reply. Check settings.');
      setActionStatuses(prev => ({
        ...prev,
        [variables.id]: { message: `Error: ${message}`, isError: true }
      }));
    }
  });

  // Dismiss Mutation (Archive/Read status update)
  const dismissMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.patch(`/gmail/messages/${id}/status`, {
        status: 'read'
      });
      return response.data;
    },
    onSuccess: (data, id) => {
      setActionStatuses(prev => ({
        ...prev,
        [id]: { message: "Action dismissed.", isError: false }
      }));
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
      setTimeout(() => {
        setActionStatuses(prev => ({ ...prev, [id]: null }));
      }, 2000);
    },
    onError: (error: any, id) => {
      console.error(error);
      const detail = error.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : (detail?.message || 'Failed to dismiss.');
      setActionStatuses(prev => ({
        ...prev,
        [id]: { message: `Error: ${message}`, isError: true }
      }));
    }
  });

  // Fetch recent messages
  const { data: messages, isLoading: isMessagesLoading } = useQuery({
    queryKey: ['recent-messages'],
    queryFn: async () => {
      const response = await apiClient.get('/gmail/messages', {
        params: { limit: 10, unread_only: true, high_priority_only: true },
      });
      return response.data;
    },
    refetchInterval: 30000,
  });

  React.useEffect(() => {
    if (messages && messages.length > 0) {
      if (seenMessageIds.current.size === 0) {
        messages.forEach((msg: any) => seenMessageIds.current.add(msg.id));
        return;
      }

      const newHighPriority = messages.find((msg: any) => {
        const isNew = !seenMessageIds.current.has(msg.id);
        seenMessageIds.current.add(msg.id);
        return isNew && (msg.priority === 'high' || msg.priority === 'critical');
      });

      if (newHighPriority) {
        setNotification({
          id: newHighPriority.id,
          sender: newHighPriority.sender,
          subject: newHighPriority.subject || '(no subject)'
        });
        const timer = setTimeout(() => setNotification(null), 6000);
        return () => clearTimeout(timer);
      }
    }
  }, [messages]);

  // Fetch connected service preferences
  const { data: preferences } = useQuery({
    queryKey: ['preferences'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/preferences');
      return response.data;
    },
  });

  // Fetch AI LLM health status
  const { data: aiHealth } = useQuery({
    queryKey: ['ai-health'],
    queryFn: async () => {
      const response = await apiClient.get('/ai/health');
      return response.data;
    },
    refetchInterval: 60000, // Check health every minute
  });

  const connectedServices = preferences?.connected_services || [];
  const isGoogleConnected = connectedServices.find((s: any) => s.provider === 'google')?.connected;
  const isTwitterConnected = connectedServices.find((s: any) => s.provider === 'twitter')?.connected;


  // Fetch AI processing job status
  const { data: jobStatus } = useQuery({
    queryKey: ['ai-job-status-dashboard'],
    queryFn: async () => {
      const response = await apiClient.get('/ai/job/status');
      return response.data;
    },
    refetchInterval: 3000,
  });

  const [bannerDismissed, setBannerDismissed] = useState(false);
  const isJobActive = jobStatus?.has_job && ['starting', 'checking_connections', 'syncing', 'processing', 'finalizing', 'background_processing'].includes(jobStatus?.state);

  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto relative z-10">
        <SyncRunAIModal isOpen={isSyncModalOpen} onClose={() => setIsSyncModalOpen(false)} />

        {/* Compact AI Job Progress Bar */}
        {isJobActive && (
          <div className="flex items-center justify-between p-3.5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 shadow-md">
            <div className="flex items-center gap-3">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              <span className="text-xs font-medium">
                AI processing in progress: {jobStatus?.current_stage}
              </span>
            </div>
            <button
              onClick={() => setIsSyncModalOpen(true)}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 underline underline-offset-4 flex items-center gap-1 cursor-pointer bg-transparent border-none"
            >
              View progress →
            </button>
          </div>
        )}

        {!bannerDismissed && aiHealth?.status === 'error' && (
          <div className="flex items-start justify-between gap-3 p-4 rounded-xl border border-rose-500/25 bg-rose-500/5 text-rose-250 shadow-sm relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-r from-rose-500/0 via-rose-500/2 to-rose-500/0 pointer-events-none"></div>
            <div className="flex items-start gap-3 z-10">
              <AlertTriangle className="w-5 h-5 text-rose-450 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h4 className="font-semibold text-rose-400 text-xs">AI Service Notice</h4>
                <p className="text-zinc-400 text-xs">
                  {aiHealth?.reason || "AI service is currently rate-limited or unavailable. Please check your settings."}
                </p>
              </div>
            </div>
            <button
              onClick={() => setBannerDismissed(true)}
              className="px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-semibold rounded-lg border border-rose-500/30 transition-all cursor-pointer z-10 shrink-0"
              aria-label="Dismiss AI Service Notice"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Welcome Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900/60 pb-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-50 via-zinc-100 to-zinc-400 bg-clip-text text-transparent">
              Welcome back{user?.full_name && typeof user.full_name === 'string' ? `, ${user.full_name.split(' ')[0]}` : ''}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Here is your executive status report and daily briefing.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shadow-sm shadow-indigo-500/5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Assistant Online
            </span>
            <button 
              onClick={() => setIsSyncModalOpen(true)}
              disabled={isJobActive}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white shadow-lg shadow-indigo-600/20 transition-all cursor-pointer border border-indigo-500/30"
            >
              {isJobActive ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Syncing & analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
                  Sync & Run AI
                </>
              )}
            </button>
          </div>
        </div>

        {(syncStatus || aiStatus) && (
          <div className={`flex items-start gap-3 p-4 rounded-xl border ${
            (syncStatus?.includes('failed') || aiStatus?.includes('failed'))
              ? 'border-rose-500/25 bg-rose-500/5 text-rose-300 shadow-sm relative overflow-hidden group'
              : 'border-zinc-800 bg-zinc-900/40 text-zinc-300 shadow-sm'
          }`}>
            <div className="space-y-1">
              <p className="text-xs font-semibold">
                {syncStatus || aiStatus}
              </p>
            </div>
          </div>
        )}

        {/* Daily Executive Briefing */}
        <div className="glass-panel rounded-xl p-6 relative overflow-hidden group/briefing hover:border-indigo-500/25 transition-all duration-500">
          {/* Subtle Indigo glowing accent */}
          <div className="absolute -top-12 -right-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none group-hover/briefing:bg-indigo-500/15 transition-all duration-500"></div>
          
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">AI Daily Executive Briefing</h2>
          </div>

          {isBriefingLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-zinc-500">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-3" />
              <p className="text-xs font-mono tracking-widest uppercase animate-pulse">Synthesizing communications...</p>
            </div>
          ) : briefing ? (
            <div className="space-y-6 relative z-10">
              <div>
                <p className="text-base text-zinc-200 leading-relaxed font-normal">
                  {briefing.executive_summary || "No executive summary available. Please sync Gmail first."}
                </p>
              </div>

              {/* Grid of details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-5 border-t border-zinc-900/60">
                {/* Critical Items */}
                <div className="space-y-3">
                  <h3 className="text-xs font-semibold text-rose-450 uppercase tracking-widest flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> Critical Risks & Blocks
                  </h3>
                  {briefing.critical_items && briefing.critical_items.length > 0 ? (
                    <ul className="space-y-2">
                      {briefing.critical_items.map((item: any, idx: number) => (
                        <li key={idx} className="text-sm text-zinc-300 flex items-start gap-2">
                          <span className="text-rose-500 mt-1">•</span>
                          <span>
                            {typeof item === 'object' && item !== null ? (
                              <>
                                <strong className="text-zinc-200">{item.item || item.action}</strong>
                                {item.deadline && (
                                  <span className="text-[10px] text-rose-450 ml-1.5 px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 font-mono">
                                    Deadline: {item.deadline}
                                  </span>
                                )}
                                {item.action && item.item && (
                                  <span className="block text-[10px] text-zinc-400 mt-0.5">
                                    Action: {item.action}
                                  </span>
                                )}
                              </>
                            ) : (
                              String(item)
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-zinc-550 italic">No critical risks identified.</p>
                  )}
                </div>

                {/* Recommended Priorities */}
                <div className="space-y-3">
                  <h3 className="text-xs font-semibold text-indigo-400 uppercase tracking-widest flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5" /> Recommended Focus Areas
                  </h3>
                  {briefing.recommended_priorities && briefing.recommended_priorities.length > 0 ? (
                    <ul className="space-y-2">
                      {briefing.recommended_priorities.map((item: any, idx: number) => (
                        <li key={idx} className="text-sm text-zinc-300 flex items-start gap-2">
                          <span className="text-indigo-500 mt-1">•</span>
                          <span>
                            {typeof item === 'object' && item !== null ? (
                              <>
                                <strong className="text-zinc-200">{item.what || item.item}</strong>
                                {item.when && (
                                  <span className="text-[10px] text-indigo-400 ml-1.5 px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 font-mono">
                                    {item.when}
                                  </span>
                                )}
                              </>
                            ) : (
                              String(item)
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-zinc-555 italic">No priorities recommended.</p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center border border-dashed border-zinc-800/80 rounded-lg p-6">
              <Sparkles className="w-8 h-8 text-zinc-600 mx-auto mb-3 animate-pulse" />
              <p className="text-sm text-zinc-300 font-medium">No Executive Briefing Generated Yet</p>
              <p className="text-xs text-zinc-500 mt-1.5 max-w-sm mx-auto">
                Connect your Google account in Settings, sync emails in the Inbox, and generate your first briefing.
              </p>
              <Link 
                href="/settings"
                className="inline-flex items-center gap-1.5 mt-4 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-all hover:underline"
              >
                Go to integrations center
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>

        {/* SECTION 2: AUTO PILOT OVERVIEW */}
        <div className="glass-panel rounded-xl p-6 relative overflow-hidden border border-zinc-850 hover:border-indigo-500/20 transition-all duration-300">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2.5">
                <Bot className="w-4 h-4 text-indigo-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Auto Pilot</h2>
                
                {autopilotSummary?.status === 'active' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    ACTIVE
                  </span>
                )}
                {autopilotSummary?.status === 'paused' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 border border-amber-500/20 text-amber-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500"></span>
                    OFF
                  </span>
                )}
                {autopilotSummary?.status === 'waiting_for_connection' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-zinc-800 border border-zinc-700 text-zinc-400">
                    WAITING FOR CONNECTION
                  </span>
                )}
              </div>

              <p className="text-xs text-zinc-400 leading-relaxed">
                {autopilotSummary?.status === 'active'
                  ? 'Continuous background monitoring across your connected applications.'
                  : autopilotSummary?.status === 'waiting_for_connection'
                  ? 'No connected applications available for Auto Pilot.'
                  : 'Auto Pilot is currently disabled.'}
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              {autopilotSummary?.status === 'waiting_for_connection' ? (
                <Link
                  href="/settings"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all"
                >
                  Connect Applications
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <Link
                  href="/autopilot"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-200 transition-all"
                >
                  View Auto Pilot
                  <ArrowRight className="w-3.5 h-3.5 text-indigo-400" />
                </Link>
              )}
            </div>
          </div>

          {/* Quick Metrics Bar */}
          {autopilotSummary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-5 mt-5 border-t border-zinc-900/60 text-xs">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Monitored</span>
                <p className="font-semibold text-zinc-200 mt-0.5">
                  {autopilotSummary.active_sources_count > 0
                    ? `${autopilotSummary.active_sources_count} source(s)`
                    : 'None active'}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Processed Today</span>
                <p className="font-semibold text-zinc-200 mt-0.5 font-mono">
                  {autopilotSummary.processed_today_count || 0} items
                </p>
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Drafts Generated</span>
                <p className="font-semibold text-indigo-400 mt-0.5 font-mono">
                  {autopilotSummary.actions_taken_count || 0} drafts
                </p>
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Needs Attention</span>
                <p className="font-semibold text-amber-400 mt-0.5 font-mono">
                  {autopilotSummary.pending_review_count || 0} waiting
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Recent High Priority Messages */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-zinc-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Proactive Action Queue</h2>
              </div>
              <Link href="/inbox" className="text-xs font-semibold text-indigo-455 hover:text-indigo-300 flex items-center gap-0.5 transition-all">
                Open Inbox
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="space-y-4">
              {isMessagesLoading ? (
                <div className="glass-panel rounded-xl p-12 flex justify-center text-zinc-500">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
                </div>
              ) : messages && messages.length > 0 ? (
                messages.map((msg: any) => {
                  const status = actionStatuses[msg.id];
                  const isPending = approveMutation.isPending && approveMutation.variables?.id === msg.id || dismissMutation.isPending && dismissMutation.variables === msg.id;

                  return (
                    <div 
                      key={msg.id} 
                      className="glass-panel rounded-xl p-5 space-y-4 border-l-2 border-transparent hover:border-indigo-500/40 transition-all duration-300 relative overflow-hidden"
                    >
                      {/* Top Row: Sender, Source, Priority, Date */}
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-2.5">
                          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                            msg.source === 'gmail' ? 'bg-red-950/20 text-red-400 border-red-900/20' :
                            msg.source === 'whatsapp' ? 'bg-green-950/20 text-green-400 border-green-900/20' :
                            'bg-sky-950/20 text-sky-400 border-sky-900/20'
                          }`}>
                            {msg.source}
                          </span>
                          <span className="text-xs font-bold text-zinc-200">{msg.sender}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                            msg.priority === 'critical' ? 'border-rose-900/30 bg-rose-950/20 text-rose-400' :
                            msg.priority === 'high' ? 'border-amber-900/30 bg-amber-950/20 text-amber-400' :
                            'border-zinc-800 bg-zinc-900/50 text-zinc-400'
                          }`}>
                            {msg.priority}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-500">
                            {msg.received_at ? new Date(msg.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>
                      </div>

                      {/* Content Body */}
                      <div className="space-y-1">
                        {msg.subject && (
                          <h4 className="text-xs font-bold text-zinc-100">{msg.subject}</h4>
                        )}
                        <p className="text-xs text-zinc-300 leading-relaxed line-clamp-3">{msg.body}</p>
                      </div>

                      {/* AI Summary Section (Collapsible) */}
                      {msg.summary && (
                        <div className="border-t border-zinc-900/60 pt-3">
                          <button
                            onClick={() => setExpandedSummary(prev => ({ ...prev, [msg.id]: !prev[msg.id] }))}
                            className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200 font-semibold cursor-pointer transition-colors"
                          >
                            {expandedSummary[msg.id] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                            {expandedSummary[msg.id] ? "Hide AI Insights" : "Show AI Insights"}
                          </button>
                          
                          {expandedSummary[msg.id] && (
                            <div className="mt-2.5 space-y-2 bg-zinc-950/40 rounded-lg p-3 border border-zinc-900/40 text-[11px] leading-relaxed">
                              <p><span className="font-semibold text-indigo-400">Summary:</span> {msg.summary}</p>
                              {msg.category && (
                                <p><span className="font-semibold text-indigo-400">Category:</span> <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[10px]">{msg.category}</span></p>
                              )}
                              {msg.sentiment && (
                                <p><span className="font-semibold text-indigo-400">Sentiment:</span> <span className="capitalize">{msg.sentiment}</span></p>
                              )}
                              {msg.action_items && (
                                <div>
                                  <span className="font-semibold text-indigo-400 block mb-0.5">Action Items:</span>
                                  <p className="whitespace-pre-line text-zinc-400">{msg.action_items}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Editable AI Draft Reply */}
                      <div className="space-y-2 border-t border-zinc-900/60 pt-3">
                        <div className="flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Suggested Draft Reply</span>
                        </div>
                        <textarea
                          disabled={isPending}
                          value={draftEdits[msg.id] !== undefined ? draftEdits[msg.id] : (msg.suggested_reply || '')}
                          onChange={(e) => setDraftEdits(prev => ({ ...prev, [msg.id]: e.target.value }))}
                          rows={4}
                          className="w-full text-xs bg-zinc-950/60 border border-zinc-900 rounded-lg p-3 text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50 transition-all font-sans leading-relaxed disabled:opacity-60"
                          placeholder="Type or edit the reply here..."
                        />
                      </div>

                      {/* Action Status Notifications */}
                      {status && (
                        <div className={`text-[11px] px-3 py-2 rounded-lg border ${
                          status.isError ? 'border-red-955 bg-red-955/20 text-red-400' : 'border-emerald-955 bg-emerald-955/20 text-emerald-400'
                        }`}>
                          {status.message}
                        </div>
                      )}

                      {/* Action Trigger Buttons */}
                      <div className="flex items-center gap-2 pt-2">
                        <button
                          disabled={isPending}
                          onClick={() => approveMutation.mutate({ id: msg.id, replyText: draftEdits[msg.id] !== undefined ? draftEdits[msg.id] : (msg.suggested_reply || '') })}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] transition-all text-white cursor-pointer disabled:opacity-50"
                        >
                          {isPending && approveMutation.variables?.id === msg.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Check className="w-3.5 h-3.5" />
                          )}
                          Approve & Send
                        </button>
                        <button
                          disabled={isPending}
                          onClick={() => dismissMutation.mutate(msg.id)}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold bg-zinc-900 border border-zinc-800 hover:border-red-900/30 hover:bg-red-950/10 hover:text-red-400 active:scale-[0.98] transition-all text-zinc-400 cursor-pointer disabled:opacity-50"
                        >
                          {isPending && dismissMutation.variables === msg.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash className="w-3.5 h-3.5" />
                          )}
                          Dismiss
                        </button>
                        <Link
                          href={`/inbox?id=${msg.id}`}
                          className="px-3 py-2 rounded-lg text-xs font-bold bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-all text-center ml-auto"
                        >
                          View Thread
                        </Link>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="glass-panel rounded-xl p-12 text-center text-zinc-555 italic text-xs border border-dashed border-zinc-800/80">
                  No proactive actions pending in your queue. All caught up!
                </div>
              )}
            </div>
          </div>

          {/* Right Pane: Connections */}
          <div className="space-y-8">
            {/* Integrations Center Status */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-zinc-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Integrations</h2>
              </div>

              <div className="glass-panel rounded-xl p-5 space-y-4">
                {connectedServices.map((service: any) => {
                  const meta = PROVIDER_METADATA[service.provider] || {
                    name: service.provider.charAt(0).toUpperCase() + service.provider.slice(1),
                    dotClass: 'bg-indigo-500',
                    containerClass: 'bg-indigo-500/20 border-indigo-500/30'
                  };
                  return (
                    <div key={service.provider} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-2.5 h-2.5 rounded-full ${meta.containerClass} flex items-center justify-center`}>
                          <div className={`w-1 h-1 rounded-full ${service.connected ? `${meta.dotClass} animate-pulse` : 'bg-zinc-700'}`}></div>
                        </div>
                        <span className="font-semibold text-zinc-350">{meta.name}</span>
                      </div>
                      <span className={`text-[9px] font-mono font-semibold px-2 py-0.5 rounded border ${
                        service.connected ? 'bg-emerald-950/20 text-emerald-455 border-emerald-900/30' : 'bg-zinc-900 border-zinc-800 text-zinc-550'
                      }`}>
                        {service.connected ? 'Connected' : 'Offline'}
                      </span>
                    </div>
                  );
                })}

                <div className="pt-3 border-t border-zinc-900/60">
                  <Link 
                    href="/settings"
                    className="flex items-center justify-center gap-1.5 w-full py-2 rounded bg-zinc-900 hover:bg-zinc-850 hover:border-zinc-700/80 text-[10px] font-bold text-zinc-300 hover:text-zinc-100 transition-all border border-zinc-800/80 cursor-pointer"
                  >
                    Manage Connections
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      {notification && (
        <Link 
          href={`/inbox?id=${notification.id}`}
          className="fixed bottom-6 right-6 z-50 max-w-sm w-full bg-zinc-950/95 border-2 border-amber-500/50 rounded-xl shadow-2xl p-4 animate-in slide-in-from-bottom duration-300 backdrop-blur-md cursor-pointer hover:border-amber-450 transition-all block"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg border border-amber-500/20 text-amber-500">
              <AlertTriangle className="w-5 h-5 animate-bounce" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">High-Priority Incoming</span>
                <button 
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setNotification(null);
                  }} 
                  className="text-zinc-550 hover:text-zinc-350 text-xs px-1"
                >
                  ×
                </button>
              </div>
              <p className="text-xs font-bold text-zinc-100 line-clamp-1">{notification.sender}</p>
              <p className="text-[11px] text-zinc-400 line-clamp-2">{notification.subject}</p>
            </div>
          </div>
        </Link>
      )}
    </SidebarLayout>
  );
}
