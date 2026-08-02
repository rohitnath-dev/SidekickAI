'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Sparkles, 
  RefreshCw, 
  AlertTriangle, 
  CheckSquare, 
  CalendarDays, 
  Clock, 
  ListTodo,
  ShieldAlert,
  HelpCircle,
  Loader2
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

export default function PlannerPage() {
  const { data: briefing, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['planner-briefing'],
    queryFn: async () => {
      const response = await apiClient.get('/planner/briefing');
      return response.data;
    },
    retry: false,
  });

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-5xl mx-auto h-full overflow-y-auto">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900/60 pb-6">
          <div>
            <span className="text-[10px] font-mono tracking-widest uppercase text-zinc-500">
              AI Operations Desk
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-50 mt-1">
              Executive Daily Briefing
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Synthesized agenda, priority queues, and communication bottlenecks.
            </p>
          </div>
          <div>
            <button
              onClick={() => refetch()}
              disabled={isLoading || isRefetching}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-zinc-100 text-zinc-950 hover:bg-zinc-200 transition-all cursor-pointer disabled:opacity-50 shadow-sm"
            >
              {isLoading || isRefetching ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Synthesizing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Regenerate Agenda
                </>
              )}
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="py-24 flex flex-col items-center justify-center text-zinc-500">
            <Loader2 className="w-10 h-10 animate-spin text-zinc-400 mb-3" />
            <p className="text-xs font-mono tracking-widest uppercase">Aggregating cross-platform context...</p>
          </div>
        ) : briefing ? (
          <div className="space-y-8">
            
            {/* Date Tag */}
            {briefing.date && (
              <div className="inline-block bg-zinc-900 border border-zinc-800 rounded px-3 py-1 text-xs font-mono text-zinc-350">
                DATE OF REPORT: {new Date(briefing.date).toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </div>
            )}

            {/* Executive Summary */}
            <div className="glass-panel rounded-xl p-6 relative overflow-hidden group/summary hover:border-indigo-500/20 transition-all duration-500">
              <div className="absolute -top-12 -right-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none group-hover/summary:bg-indigo-500/15 transition-all duration-500"></div>
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Executive Intelligence Summary</h2>
              </div>
              <p className="text-base text-zinc-200 leading-relaxed font-normal">
                {briefing.executive_summary || 'Sync your communications first to enable AI executive brief summarization.'}
              </p>
            </div>

            {/* Grid of Focus Areas */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              
              {/* Critical Risks & Blocks */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <AlertTriangle className="w-4 h-4 text-rose-450 animate-pulse" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Critical Risks & Blocks</h3>
                </div>
                {briefing.critical_items && briefing.critical_items.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.critical_items.map((item: any, idx: number) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2.5 leading-relaxed">
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
                  <p className="text-xs text-zinc-550 italic">No urgent bottlenecks identified.</p>
                )}
              </div>

              {/* Recommended Priorities */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <ListTodo className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Recommended Priorities</h3>
                </div>
                {briefing.recommended_priorities && briefing.recommended_priorities.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.recommended_priorities.map((item: string, idx: number) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2.5 leading-relaxed">
                        <span className="text-indigo-500 mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-550 italic">No priorities recommended.</p>
                )}
              </div>

              {/* Upcoming Deadlines */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <Clock className="w-4 h-4 text-amber-450" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Upcoming Milestones & Deadlines</h3>
                </div>
                {briefing.upcoming_deadlines && briefing.upcoming_deadlines.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.upcoming_deadlines.map((item: any, idx: number) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2.5 leading-relaxed">
                        <span className="text-amber-500 mt-1">•</span>
                        <span>
                          {typeof item === 'object' && item !== null ? (
                            <>
                              <strong className="text-zinc-200">{item.what || item.item}</strong>
                              {item.when && (
                                <span className="text-[10px] text-amber-450 ml-1.5 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 font-mono">
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
                  <p className="text-xs text-zinc-550 italic">No upcoming deadlines detected.</p>
                )}
              </div>

              {/* Next Action Checklists */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <CheckSquare className="w-4 h-4 text-emerald-450" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Suggested Next Actions</h3>
                </div>
                {briefing.next_actions && briefing.next_actions.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.next_actions.map((item: string, idx: number) => (
                      <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-300">
                        <input 
                          type="checkbox" 
                          className="mt-0.5 accent-indigo-500 rounded border-zinc-800 bg-zinc-950 w-3.5 h-3.5 focus:ring-0" 
                        />
                        <span className="leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-550 italic">No next actions recommended.</p>
                )}
              </div>

              {/* Pending Work */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <CalendarDays className="w-4 h-4 text-sky-450" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Pending Work items</h3>
                </div>
                {briefing.pending_work && briefing.pending_work.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.pending_work.map((item: string, idx: number) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2.5 leading-relaxed">
                        <span className="text-sky-500 mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-550 italic">No pending items.</p>
                )}
              </div>

              {/* Key Risks */}
              <div className="glass-panel rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900/60 pb-3">
                  <ShieldAlert className="w-4 h-4 text-purple-450" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">Threat & Risk Matrix</h3>
                </div>
                {briefing.risks && briefing.risks.length > 0 ? (
                  <ul className="space-y-3">
                    {briefing.risks.map((item: string, idx: number) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2.5 leading-relaxed">
                        <span className="text-purple-500 mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-550 italic">No risks identified.</p>
                )}
              </div>

            </div>
          </div>
        ) : (
          <div className="py-16 text-center border border-dashed border-zinc-800 rounded-lg p-8">
            <Sparkles className="w-10 h-10 text-zinc-700 mx-auto mb-3 animate-pulse" />
            <h3 className="text-sm font-semibold text-zinc-300">No Daily Briefing Found</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
              We need context to compile your agenda. Go to Settings, connect Google and instant messengers, then synchronize your inbox to populate data.
            </p>
          </div>
        )}

      </div>
    </SidebarLayout>
  );
}
