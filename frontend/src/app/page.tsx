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
  ChevronUp
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

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
  },
  whatsapp: {
    name: 'WhatsApp API',
    dotClass: 'bg-green-500',
    containerClass: 'bg-green-500/20 border-green-500/30'
  },
  linkedin: {
    name: 'LinkedIn Profile',
    dotClass: 'bg-blue-500',
    containerClass: 'bg-blue-500/20 border-blue-500/30'
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

  // Fetch today's calendar events
  const { data: events, isLoading: isEventsLoading, error: eventsError } = useQuery({
    queryKey: ['calendar-today'],
    queryFn: async () => {
      const response = await apiClient.get('/calendar/today');
      return response.data;
    },
    retry: false,
  });

  const queryClient = useQueryClient();
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

  const connectedServices = preferences?.connected_services || [];
  const isGoogleConnected = connectedServices.find((s: any) => s.provider === 'google')?.connected;
  const isTwitterConnected = connectedServices.find((s: any) => s.provider === 'twitter')?.connected;
  const isWhatsAppConnected = connectedServices.find((s: any) => s.provider === 'whatsapp')?.connected;

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto relative z-10">
        {/* Welcome Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900/60 pb-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-50 via-zinc-100 to-zinc-400 bg-clip-text text-transparent">
              Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
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
              onClick={() => refetchBriefing()}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-zinc-100 text-zinc-950 hover:bg-zinc-200 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer shadow-md shadow-zinc-950/20"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Regenerate Briefing
            </button>
          </div>
        </div>

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

          {/* Right Pane: Calendar & Connections */}
          <div className="space-y-8">
            {/* Calendar Widget */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-zinc-400" />
                  <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Schedule Today</h2>
                </div>
              </div>

              <div className="glass-panel rounded-xl p-5 space-y-3.5">
                {isEventsLoading ? (
                  <div className="flex justify-center py-6">
                    <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                  </div>
                ) : eventsError || !isGoogleConnected ? (
                  (() => {
                    const errorDetails = (eventsError as any)?.response?.data?.errorDetails;
                    const isApiDisabled = errorDetails?.code === 'GOOGLE_API_DISABLED';
                    const isSessionExpired = errorDetails?.code === 'GOOGLE_SESSION_EXPIRED';
                    const buttonText = isApiDisabled ? 'Enable API' : (isSessionExpired ? 'Reconnect' : 'Connect Google');
                    const linkHref = isApiDisabled && errorDetails.actionUrl ? errorDetails.actionUrl : '/settings';
                    const target = isApiDisabled ? '_blank' : '_self';
                    const rel = isApiDisabled ? 'noreferrer' : undefined;
                    
                    return (
                      <div className="py-6 text-center border border-dashed border-zinc-800/80 rounded-lg p-5">
                        <Calendar className="w-8 h-8 text-zinc-650 mx-auto mb-2 animate-pulse" />
                        <p className="text-xs font-semibold text-zinc-300">
                          {errorDetails?.message || (eventsError as any)?.response?.data?.detail || "Calendar Disconnected"}
                        </p>
                        <p className="text-[10px] text-zinc-500 mt-1 max-w-[200px] mx-auto">
                          {isApiDisabled 
                            ? "The Google Calendar API needs to be enabled in your Google Cloud Console." 
                            : (isSessionExpired ? "Your Google authentication session has expired." : "Connect Google Workspace to sync today's timeline.")}
                        </p>
                        {isApiDisabled && errorDetails.actionUrl ? (
                          <a 
                            href={linkHref}
                            target={target}
                            rel={rel}
                            className="inline-block mt-3 px-3 py-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-[10px] text-zinc-300 font-semibold rounded-md transition-all hover:text-zinc-100 cursor-pointer"
                          >
                            {buttonText}
                          </a>
                        ) : (
                          <Link 
                            href={linkHref}
                            className="inline-block mt-3 px-3 py-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-[10px] text-zinc-300 font-semibold rounded-md transition-all hover:text-zinc-100 cursor-pointer"
                          >
                            {buttonText}
                          </Link>
                        )}
                      </div>
                    );
                  })()
                ) : events && events.length > 0 ? (
                  <div className="space-y-4">
                    {events.map((event: any) => {
                      const startTime = new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      const endTime = new Date(event.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      return (
                        <div key={event.id} className="group relative flex flex-col gap-1 pl-3.5 border-l-2 border-indigo-500/40 hover:border-indigo-400 transition-all duration-300">
                          <p className="text-xs font-semibold text-zinc-200 group-hover:text-zinc-100 transition-colors">{event.title}</p>
                          <p className="text-[10px] font-mono text-zinc-400">{startTime} — {endTime}</p>
                          {event.location && (
                            <p className="text-[10px] text-zinc-550 truncate mt-0.5">{event.location}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-zinc-550 italic py-6 text-center">No calendar events scheduled today.</p>
                )}
              </div>
            </div>

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
