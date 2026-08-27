'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { 
  Sparkles, 
  RefreshCw, 
  AlertTriangle, 
  CheckSquare, 
  CalendarDays, 
  Clock, 
  ListTodo,
  ShieldAlert,
  Loader2,
  Plus,
  Check,
  Trash2,
  Edit2,
  Calendar,
  ArrowRight,
  UserCheck,
  Flame,
  CheckCircle2,
  Clock3,
  Search,
  ExternalLink,
  MessageSquare,
  AlertCircle,
  X
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';
import SyncRunAIModal from '@/components/sync-run-ai-modal';

export default function PlannerPage() {
  const queryClient = useQueryClient();

  // Tab State
  const [activeTab, setActiveTab] = useState<'today' | 'week' | 'deadlines' | 'waiting' | 'all'>('today');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);

  // Modal State
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<any | null>(null);

  // Task Form State
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskPriority, setTaskPriority] = useState('medium');
  const [taskStatus, setTaskStatus] = useState('pending');
  const [taskSource, setTaskSource] = useState('manual');
  const [taskDueDate, setTaskDueDate] = useState('');
  const [taskScheduledTime, setTaskScheduledTime] = useState('');
  const [taskDuration, setTaskDuration] = useState(30);
  const [taskContextReason, setTaskContextReason] = useState('');
  const [taskWaitingOn, setTaskWaitingOn] = useState('');

  // Fetch Dashboard Planning Data
  const { data: dashboard, isLoading: isDashboardLoading, refetch: refetchDashboard, isRefetching } = useQuery({
    queryKey: ['planner-dashboard'],
    queryFn: async () => {
      const response = await apiClient.get('/planner/dashboard');
      return response.data;
    },
    refetchInterval: 30000,
  });

  // Fetch Daily Briefing for summary section
  const { data: briefing } = useQuery({
    queryKey: ['planner-briefing-summary'],
    queryFn: async () => {
      const response = await apiClient.get('/planner/briefing');
      return response.data;
    },
    retry: false,
  });

  // Mutations
  const planMyDayMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/planner/plan-my-day');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['planner-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['recent-messages'] });
    },
  });

  const completeTaskMutation = useMutation({
    mutationFn: async (taskId: number) => {
      const response = await apiClient.post(`/planner/tasks/${taskId}/complete`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['planner-dashboard'] });
    },
  });

  const snoozeTaskMutation = useMutation({
    mutationFn: async (taskId: number) => {
      const response = await apiClient.post(`/planner/tasks/${taskId}/snooze`, { days: 1 });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['planner-dashboard'] });
    },
  });

  const deleteTaskMutation = useMutation({
    mutationFn: async (taskId: number) => {
      const response = await apiClient.delete(`/planner/tasks/${taskId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['planner-dashboard'] });
    },
  });

  const saveTaskMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        title: taskTitle,
        description: taskDescription,
        priority: taskPriority,
        status: taskStatus,
        source: taskSource,
        due_date: taskDueDate || null,
        scheduled_time: taskScheduledTime || null,
        duration_minutes: Number(taskDuration),
        context_reason: taskContextReason,
        waiting_on: taskWaitingOn,
      };

      if (editingTask) {
        const response = await apiClient.patch(`/planner/tasks/${editingTask.id}`, payload);
        return response.data;
      } else {
        const response = await apiClient.post('/planner/tasks', payload);
        return response.data;
      }
    },
    onSuccess: () => {
      setIsTaskModalOpen(false);
      resetTaskForm();
      queryClient.invalidateQueries({ queryKey: ['planner-dashboard'] });
    },
  });

  const resetTaskForm = () => {
    setEditingTask(null);
    setTaskTitle('');
    setTaskDescription('');
    setTaskPriority('medium');
    setTaskStatus('pending');
    setTaskSource('manual');
    setTaskDueDate('');
    setTaskScheduledTime('');
    setTaskDuration(30);
    setTaskContextReason('');
    setTaskWaitingOn('');
  };

  const openCreateModal = () => {
    resetTaskForm();
    setIsTaskModalOpen(true);
  };

  const openEditModal = (task: any) => {
    setEditingTask(task);
    setTaskTitle(task.title || '');
    setTaskDescription(task.description || '');
    setTaskPriority(task.priority || 'medium');
    setTaskStatus(task.status || 'pending');
    setTaskSource(task.source || 'manual');
    setTaskDueDate(task.due_date ? task.due_date.split('T')[0] : '');
    setTaskScheduledTime(task.scheduled_time || '');
    setTaskDuration(task.duration_minutes || 30);
    setTaskContextReason(task.context_reason || '');
    setTaskWaitingOn(task.waiting_on || '');
    setIsTaskModalOpen(true);
  };

  const stats = dashboard?.stats || { total: 0, pending: 0, completed: 0, overdue: 0, waiting: 0 };
  const nextBest = dashboard?.next_best_action;
  const conflicts = dashboard?.conflicts || [];
  const timeBlocks = dashboard?.time_blocks || [];
  const weeklyOverview = dashboard?.weekly_overview || [];
  const deadlines = dashboard?.deadlines || { today: [], tomorrow: [], this_week: [], later: [] };
  const todayPlan = dashboard?.today_plan || [];
  const overdueTasks = dashboard?.overdue_tasks || [];
  const waitingTasks = dashboard?.waiting_tasks || [];
  const allTasks = dashboard?.all_tasks || [];

  const filteredAllTasks = allTasks.filter((t: any) => {
    const q = searchQuery.toLowerCase();
    return (t.title || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q) || (t.source || '').toLowerCase().includes(q);
  });

  return (
    <SidebarLayout>
      <SyncRunAIModal isOpen={isSyncModalOpen} onClose={() => setIsSyncModalOpen(false)} />

      <div className="p-4 sm:p-6 md:p-8 space-y-6 max-w-7xl mx-auto h-full overflow-y-auto z-10 relative select-none">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900/80 pb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest uppercase px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-semibold">
                Executive AI Planner
              </span>
              {dashboard?.formatted_date && (
                <span className="text-xs font-mono text-zinc-500">
                  • {dashboard.formatted_date}
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-50 mt-1.5">
              Intelligent Execution Workspace
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
              Cross-platform task orchestration, smart time blocking, and automated priority management.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => planMyDayMutation.mutate()}
              disabled={planMyDayMutation.isPending || isRefetching}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all cursor-pointer border border-indigo-500/30 disabled:opacity-50"
            >
              {planMyDayMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Optimizing schedule...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
                  Plan My Day
                </>
              )}
            </button>

            <button
              onClick={openCreateModal}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-850 text-zinc-200 border border-zinc-800 transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 text-indigo-400" />
              Add Task
            </button>

            <button
              onClick={() => setIsSyncModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-850 text-zinc-300 border border-zinc-800 transition-all cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-zinc-400" />
              Sync & Run AI
            </button>
          </div>
        </div>

        {/* Stats Summary Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="glass-panel p-3.5 rounded-xl space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">Total Tasks</span>
            <p className="text-lg font-bold text-zinc-100 font-mono">{stats.total}</p>
          </div>
          <div className="glass-panel p-3.5 rounded-xl space-y-1 border-l-2 border-indigo-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold">Pending</span>
            <p className="text-lg font-bold text-indigo-300 font-mono">{stats.pending}</p>
          </div>
          <div className="glass-panel p-3.5 rounded-xl space-y-1 border-l-2 border-emerald-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold">Completed</span>
            <p className="text-lg font-bold text-emerald-300 font-mono">{stats.completed}</p>
          </div>
          <div className="glass-panel p-3.5 rounded-xl space-y-1 border-l-2 border-rose-500">
            <span className="text-[10px] font-mono uppercase tracking-wider text-rose-450 font-semibold">Overdue</span>
            <p className="text-lg font-bold text-rose-400 font-mono">{stats.overdue}</p>
          </div>
          <div className="glass-panel p-3.5 rounded-xl space-y-1 border-l-2 border-amber-500 col-span-2 sm:col-span-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold">Waiting / Blocked</span>
            <p className="text-lg font-bold text-amber-300 font-mono">{stats.waiting}</p>
          </div>
        </div>

        {/* Planning Conflict Alerts */}
        {conflicts && conflicts.length > 0 && (
          <div className="space-y-2">
            {conflicts.map((conf: any, idx: number) => (
              <div 
                key={idx}
                className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                  conf.severity === 'critical' ? 'border-rose-500/40 bg-rose-500/10 text-rose-200' :
                  conf.severity === 'high' ? 'border-amber-500/40 bg-amber-500/10 text-amber-200' :
                  'border-indigo-500/30 bg-indigo-500/10 text-indigo-200'
                }`}
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-xs font-bold uppercase tracking-wider">{conf.title}</h4>
                    <p className="text-xs opacity-90 leading-relaxed">{conf.description}</p>
                  </div>
                </div>
                {conf.action && (
                  <button 
                    onClick={() => planMyDayMutation.mutate()}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-zinc-950/80 border border-zinc-800 hover:bg-zinc-900 text-zinc-200 shrink-0 transition-all cursor-pointer"
                  >
                    {conf.action}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Next Best Action Banner */}
        {nextBest && nextBest.task && (
          <div className="glass-panel rounded-2xl p-5 relative overflow-hidden group/next border-l-4 border-l-indigo-500 hover:border-indigo-500/40 transition-all duration-300">
            <div className="absolute -top-12 -right-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none group-hover/next:bg-indigo-500/15 transition-all"></div>
            
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
              <div className="space-y-2 max-w-3xl">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">
                    Next Best Action Recommendation
                  </span>
                  <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-bold ${
                    nextBest.task.priority === 'critical' ? 'bg-rose-950/40 text-rose-400 border-rose-900/40' :
                    nextBest.task.priority === 'high' ? 'bg-amber-950/40 text-amber-400 border-amber-900/40' :
                    'bg-indigo-950/40 text-indigo-400 border-indigo-900/40'
                  }`}>
                    {nextBest.task.priority} priority
                  </span>
                </div>

                <h3 className="text-base sm:text-lg font-bold text-zinc-100">{nextBest.task.title}</h3>
                <p className="text-xs text-zinc-400 leading-relaxed font-mono text-[11px]">
                  REASON: {nextBest.reason}
                </p>
              </div>

              <div className="flex items-center gap-2.5 shrink-0">
                <button
                  onClick={() => completeTaskMutation.mutate(nextBest.task.id)}
                  disabled={completeTaskMutation.isPending}
                  className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20 transition-all cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                  Execute Now
                </button>

                {nextBest.task.source === 'gmail' && (
                  <Link
                    href={`/inbox?id=${nextBest.task.source_item_id?.replace('msg_', '')}`}
                    className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-300 transition-all"
                  >
                    <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                    Open Thread
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}

        {/* View Switcher Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-900/80 pb-3">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
            <button
              onClick={() => setActiveTab('today')}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'today'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-zinc-850'
              }`}
            >
              Today's Plan ({todayPlan.length})
            </button>

            <button
              onClick={() => setActiveTab('week')}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'week'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-zinc-850'
              }`}
            >
              This Week
            </button>

            <button
              onClick={() => setActiveTab('deadlines')}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'deadlines'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-zinc-850'
              }`}
            >
              Deadlines & Milestones
            </button>

            <button
              onClick={() => setActiveTab('waiting')}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'waiting'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-zinc-850'
              }`}
            >
              Waiting & Blocked ({waitingTasks.length})
            </button>

            <button
              onClick={() => setActiveTab('all')}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'all'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-zinc-850'
              }`}
            >
              All Tasks ({allTasks.length})
            </button>
          </div>

          {activeTab === 'all' && (
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search tasks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-indigo-500/50 transition-all"
              />
            </div>
          )}
        </div>

        {/* TAB 1: TODAY'S PLAN */}
        {activeTab === 'today' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Left Column: Today's Tasks List */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                  <ListTodo className="w-4 h-4 text-indigo-400" />
                  Today's Priority Agenda
                </h3>
                <span className="text-[10px] font-mono text-zinc-500">{todayPlan.length} items scheduled</span>
              </div>

              {isDashboardLoading ? (
                <div className="glass-panel p-12 flex justify-center text-zinc-500 rounded-xl">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
                </div>
              ) : todayPlan.length > 0 ? (
                <div className="space-y-3">
                  {todayPlan.map((task: any) => (
                    <div 
                      key={task.id}
                      className={`glass-panel rounded-xl p-4 space-y-3 border-l-2 hover:border-indigo-500/40 transition-all duration-200 ${
                        task.priority === 'critical' ? 'border-l-rose-500' :
                        task.priority === 'high' ? 'border-l-amber-500' :
                        task.status === 'completed' ? 'border-l-emerald-500 opacity-60' : 'border-l-zinc-700'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                            task.source === 'gmail' ? 'bg-red-950/20 text-red-400 border-red-900/20' :
                            task.source === 'calendar' ? 'bg-sky-950/20 text-sky-400 border-sky-900/20' :
                            task.source === 'telegram' ? 'bg-sky-950/20 text-sky-400 border-sky-900/20' :
                            'bg-zinc-900 border-zinc-800 text-zinc-400'
                          }`}>
                            {task.source}
                          </span>

                          <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                            task.priority === 'critical' ? 'bg-rose-950/30 text-rose-400 border-rose-900/30' :
                            task.priority === 'high' ? 'bg-amber-950/30 text-amber-400 border-amber-900/30' :
                            'bg-zinc-900 text-zinc-400 border-zinc-800'
                          }`}>
                            {task.priority}
                          </span>

                          <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                            task.status === 'completed' ? 'bg-emerald-950/30 text-emerald-400 border-emerald-900/30' :
                            task.status === 'in_progress' ? 'bg-indigo-950/30 text-indigo-400 border-indigo-900/30' :
                            task.status === 'waiting' ? 'bg-amber-950/30 text-amber-400 border-amber-900/30' :
                            'bg-zinc-900 text-zinc-400 border-zinc-800'
                          }`}>
                            {task.status}
                          </span>
                        </div>

                        {task.due_date && (
                          <span className="text-[10px] font-mono text-zinc-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Due: {new Date(task.due_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>

                      <div>
                        <h4 className={`text-xs font-bold text-zinc-100 ${task.status === 'completed' ? 'line-through' : ''}`}>
                          {task.title}
                        </h4>
                        {task.description && (
                          <p className="text-xs text-zinc-400 mt-1 leading-relaxed line-clamp-2">{task.description}</p>
                        )}
                        {task.context_reason && (
                          <p className="text-[11px] font-mono text-zinc-500 mt-1 italic">
                            Context: {task.context_reason}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-2 pt-2 border-t border-zinc-900/60">
                        {task.status !== 'completed' && (
                          <button
                            onClick={() => completeTaskMutation.mutate(task.id)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-900/40 text-emerald-400 text-[11px] font-semibold transition-all cursor-pointer"
                          >
                            <Check className="w-3 h-3" />
                            Complete
                          </button>
                        )}

                        <button
                          onClick={() => snoozeTaskMutation.mutate(task.id)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-[11px] font-semibold transition-all cursor-pointer"
                        >
                          <Clock3 className="w-3 h-3" />
                          Snooze 1d
                        </button>

                        <button
                          onClick={() => openEditModal(task)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-[11px] font-semibold transition-all cursor-pointer"
                        >
                          <Edit2 className="w-3 h-3" />
                          Edit
                        </button>

                        <button
                          onClick={() => deleteTaskMutation.mutate(task.id)}
                          className="p-1 rounded hover:bg-rose-950/20 text-zinc-500 hover:text-rose-400 transition-all cursor-pointer ml-auto"
                          title="Delete task"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="glass-panel p-12 rounded-xl text-center border border-dashed border-zinc-800/80 space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto animate-pulse" />
                  <p className="text-xs font-semibold text-zinc-200">Your agenda is all clear for today!</p>
                  <p className="text-[11px] text-zinc-500">Click "Plan My Day" or "Sync & Run AI" to extract new actionable items.</p>
                </div>
              )}
            </div>

            {/* Right Column: Smart Time Blocking Schedule */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400" />
                Smart Time Blocking
              </h3>

              <div className="glass-panel rounded-xl p-4 space-y-3">
                {timeBlocks.map((block: any, idx: number) => (
                  <div key={idx} className="flex items-start gap-3 text-xs p-2.5 rounded-lg bg-zinc-900/30 border border-zinc-850/60">
                    <span className="font-mono text-[10px] text-indigo-400 font-semibold shrink-0 w-24">
                      {block.time_slot}
                    </span>
                    <div className="space-y-0.5 min-w-0 flex-1">
                      <p className="font-semibold text-zinc-200 truncate">{block.title}</p>
                      {block.suggested_action && (
                        <p className="text-[10px] text-zinc-500 truncate">{block.suggested_action}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* TAB 2: THIS WEEK */}
        {activeTab === 'week' && (
          <div className="space-y-6">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <CalendarDays className="w-4 h-4 text-indigo-400" />
              Weekly Workload & Milestones Outlook
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-7 gap-3">
              {weeklyOverview.map((item: any) => (
                <div 
                  key={item.day}
                  className={`glass-panel p-4 rounded-xl space-y-2 border-t-2 ${
                    item.has_critical ? 'border-t-rose-500 bg-rose-500/5' : 'border-t-indigo-500'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-zinc-200">{item.day}</span>
                    <span className="text-[10px] font-mono text-zinc-500">{item.date.slice(5)}</span>
                  </div>
                  <div className="pt-2 border-t border-zinc-900/60">
                    <p className="text-lg font-extrabold text-zinc-100 font-mono">{item.task_count}</p>
                    <p className="text-[10px] text-zinc-500">task{item.task_count !== 1 ? 's' : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: UPCOMING DEADLINES */}
        {activeTab === 'deadlines' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Object.entries(deadlines).map(([period, items]: [string, any]) => (
              <div key={period} className="glass-panel p-5 rounded-xl space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-400 border-b border-zinc-900/60 pb-2">
                  {period.replace('_', ' ')} ({items.length})
                </h4>
                {items.length > 0 ? (
                  <ul className="space-y-2">
                    {items.map((task: any) => (
                      <li key={task.id} className="p-2.5 rounded-lg bg-zinc-900/30 border border-zinc-850 text-xs flex justify-between items-center">
                        <span className="font-semibold text-zinc-200">{task.title}</span>
                        <span className="text-[10px] font-mono text-amber-400 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                          {task.due_date ? new Date(task.due_date).toLocaleDateString() : 'No date'}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-550 italic">No deadlines for this period.</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* TAB 4: WAITING & BLOCKED */}
        {activeTab === 'waiting' && (
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-amber-400" />
              Follow-Up & Bottlenecks Queue
            </h3>

            {waitingTasks.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {waitingTasks.map((task: any) => (
                  <div key={task.id} className="glass-panel p-4 rounded-xl space-y-2 border-l-2 border-l-amber-500">
                    <div className="flex justify-between items-center text-[10px] font-mono text-zinc-500">
                      <span>STATUS: {task.status.toUpperCase()}</span>
                      {task.waiting_on && <span className="text-amber-400">Waiting on: {task.waiting_on}</span>}
                    </div>
                    <h4 className="text-xs font-bold text-zinc-100">{task.title}</h4>
                    {task.context_reason && <p className="text-xs text-zinc-400">{task.context_reason}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="glass-panel p-12 rounded-xl text-center text-xs text-zinc-550 italic border border-dashed border-zinc-800">
                No items currently blocked or waiting on external approvals.
              </div>
            )}
          </div>
        )}

        {/* TAB 5: ALL TASKS */}
        {activeTab === 'all' && (
          <div className="space-y-3">
            {filteredAllTasks.map((task: any) => (
              <div key={task.id} className="glass-panel p-4 rounded-xl flex items-center justify-between gap-4 text-xs">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-zinc-200 truncate">{task.title}</span>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">{task.priority}</span>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">{task.status}</span>
                  </div>
                  {task.description && <p className="text-zinc-400 truncate">{task.description}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => completeTaskMutation.mutate(task.id)} className="p-1.5 hover:bg-emerald-950/20 text-emerald-400 rounded">
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => deleteTaskMutation.mutate(task.id)} className="p-1.5 hover:bg-rose-950/20 text-rose-400 rounded">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>

      {/* CREATE / EDIT TASK MODAL */}
      {isTaskModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-md">
          <div className="w-full max-w-lg bg-zinc-950 border border-zinc-850 rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
              <h3 className="text-sm font-bold text-zinc-100">{editingTask ? 'Edit Task' : 'Add New Task'}</h3>
              <button onClick={() => setIsTaskModalOpen(false)} className="text-zinc-500 hover:text-zinc-200">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-zinc-400 mb-1">Title *</label>
                <input
                  type="text"
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  placeholder="Task title..."
                  className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 outline-none focus:border-indigo-500/50"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1">Description</label>
                <textarea
                  value={taskDescription}
                  onChange={(e) => setTaskDescription(e.target.value)}
                  placeholder="Task context notes..."
                  rows={3}
                  className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 outline-none focus:border-indigo-500/50"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-400 mb-1">Priority</label>
                  <select
                    value={taskPriority}
                    onChange={(e) => setTaskPriority(e.target.value)}
                    className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 outline-none"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>

                <div>
                  <label className="block text-zinc-400 mb-1">Status</label>
                  <select
                    value={taskStatus}
                    onChange={(e) => setTaskStatus(e.target.value)}
                    className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 outline-none"
                  >
                    <option value="pending">Pending</option>
                    <option value="in_progress">In Progress</option>
                    <option value="waiting">Waiting</option>
                    <option value="blocked">Blocked</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-400 mb-1">Due Date</label>
                  <input
                    type="date"
                    value={taskDueDate}
                    onChange={(e) => setTaskDueDate(e.target.value)}
                    className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-zinc-400 mb-1">Waiting On (Optional)</label>
                  <input
                    type="text"
                    value={taskWaitingOn}
                    onChange={(e) => setTaskWaitingOn(e.target.value)}
                    placeholder="e.g. Alex approval"
                    className="w-full bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-900">
              <button
                onClick={() => setIsTaskModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-zinc-900 text-zinc-300 text-xs font-semibold border border-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={() => saveTaskMutation.mutate()}
                disabled={!taskTitle || saveTaskMutation.isPending}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 disabled:opacity-50"
              >
                {saveTaskMutation.isPending ? 'Saving...' : 'Save Task'}
              </button>
            </div>
          </div>
        </div>
      )}
    </SidebarLayout>
  );
}
