'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  Inbox, 
  Search, 
  RefreshCw, 
  CheckSquare, 
  MessageSquare, 
  Mail, 
  Check, 
  ArrowLeft,
  Calendar,
  Sparkles,
  AlertTriangle,
  ShieldAlert,
  Smile,
  Globe,
  Loader2,
  Copy
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';
import DOMPurify from 'dompurify';

function InboxContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const selectedIdParam = searchParams.get('id');
  const [selectedId, setSelectedId] = useState<number | null>(
    selectedIdParam ? parseInt(selectedIdParam, 10) : null
  );



  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | { message: string, isError: boolean, action?: string, actionUrl?: string } | null>(null);

  // Smart reply states
  const [tone, setTone] = useState('professional');
  const [language, setLanguage] = useState('English');
  const [replyDraft, setReplyDraft] = useState('');
  const [isGeneratingReply, setIsGeneratingReply] = useState(false);
  const [replySuccessMsg, setReplySuccessMsg] = useState<string | null>(null);
  
  // Custom manual reply improvement state
  const [isImproving, setIsImproving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const seenMessageIds = React.useRef<Set<number>>(new Set());
  const [notification, setNotification] = useState<{ sender: string, subject: string, id: number } | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [gmailCategoryFilter, setGmailCategoryFilter] = useState('all');
  const [inboxAiLoading, setInboxAiLoading] = useState(false);
  const [inboxAiStatus, setInboxAiStatus] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('last_synced_at');
      if (stored) {
        setLastSyncedAt(stored);
      }
    }
  }, []);

  const sanitizeEmailBody = (text: string | null | undefined): string => {
    if (!text) return '';
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(text, 'text/html');
      
      // Remove stylesheet and script contents completely to avoid style bleeding
      const elementsToRemove = doc.querySelectorAll('style, script, head, link, meta');
      elementsToRemove.forEach(el => el.remove());
      
      // Convert hyperlinks from <a href="url">text</a> to "text (url)" or just "url" if text is identical
      const links = doc.querySelectorAll('a');
      links.forEach(link => {
        const href = link.getAttribute('href');
        const linkText = link.textContent?.trim();
        if (href && linkText && href !== linkText && !href.startsWith('mailto:')) {
          link.textContent = `${linkText} (${href})`;
        }
      });

      let plainText = doc.body.textContent || doc.body.innerText || '';
      
      // Clean up broken spaces and custom entities
      plainText = plainText
        .replace(/&nb\s*sp\s*;/gi, ' ') // match &nbsp; with potential spaces like &nb sp; or &nb  sp;
        .replace(/&zwnj;/gi, '')
        .replace(/\u00a0/g, ' ') // convert non-breaking spaces to regular spaces
        .replace(/&amp;/gi, '&')
        .replace(/&lt;/gi, '<')
        .replace(/&gt;/gi, '>')
        .replace(/&quot;/gi, '"')
        .replace(/&#39;/gi, "'");
      
      // Strip any residual HTML tags just in case
      plainText = plainText.replace(/<[^>]+>/g, '');

      // Format text into clean, readable plain paragraphs
      const paragraphs = plainText
        .split(/\n\s*\n/) // split by empty lines
        .map(p => p.replace(/\s+/g, ' ').trim()) // collapse multiple spaces within paragraphs
        .filter(p => p.length > 0);

      return paragraphs.join('\n\n');
    } catch (e) {
      // Fallback simple regex parsing
      return text
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
        .replace(/<[^>]+>/g, '')
        .replace(/&nb\s*sp\s*;/gi, ' ')
        .replace(/&zwnj;/gi, '')
        .replace(/\u00a0/g, ' ')
        .replace(/&amp;/gi, '&')
        .replace(/&lt;/gi, '<')
        .replace(/&gt;/gi, '>')
        .replace(/&quot;/gi, '"')
        .replace(/&#39;/gi, "'")
        .split(/\n\s*\n/)
        .map(p => p.replace(/\s+/g, ' ').trim())
        .filter(p => p.length > 0)
        .join('\n\n');
    }
  };

  const { data: messages, isLoading: isMessagesLoading, refetch: refetchMessages } = useQuery({
    queryKey: ['messages', sourceFilter, unreadOnly, gmailCategoryFilter],
    queryFn: async () => {
      const params: any = {};
      if (sourceFilter !== 'all') params.source = sourceFilter;
      if (unreadOnly) params.unread_only = true;
      if (gmailCategoryFilter !== 'all') {
        params.category = gmailCategoryFilter;
      }
      params.limit = 50;

      const response = await apiClient.get('/gmail/messages', { params });
      return response.data;
    },
    refetchInterval: 30000,
  });

  // Fetch user preferences settings to check connected integrations
  const { data: preferences } = useQuery({
    queryKey: ['preferences'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/preferences');
      return response.data;
    }
  });

  const connectedServices = preferences?.connected_services || [];
  const hasConnections = connectedServices.some((service: any) => service.connected);

  // Fetch active message detail
  const { data: selectedMessage, isLoading: isDetailLoading, refetch: refetchDetail } = useQuery({
    queryKey: ['message-detail', selectedId],
    queryFn: async () => {
      if (!selectedId) return null;
      const response = await apiClient.get(`/gmail/messages/${selectedId}`);
      return response.data;
    },
    enabled: !!selectedId,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (messages && messages.length > 0) {
      if (seenMessageIds.current.size === 0) {
        messages.forEach((msg: any) => seenMessageIds.current.add(msg.id));
        return;
      }

      const newHighPriority = messages.find((msg: any) => {
        const isNew = !seenMessageIds.current.has(msg.id);
        seenMessageIds.current.add(msg.id);
        return isNew && (msg.priority === 'high' || msg.priority === 'critical') && msg.status === 'unread';
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


  // Sync messages
  const syncMutation = useMutation({
    mutationFn: async () => {
      setSyncLoading(true);
      
      const isTelegramConnected = connectedServices.some((s: any) => s.provider === 'telegram' && s.connected);
      const isGoogleConnected = connectedServices.some((s: any) => s.provider === 'google' && s.connected);
      const isTwitterConnected = connectedServices.some((s: any) => s.provider === 'twitter' && s.connected);
      
      if (sourceFilter === 'telegram') {
        if (!isTelegramConnected) {
          throw new Error('Telegram is not connected. Connect it in Settings.');
        }
        setSyncStatus('Syncing Telegram updates...');
        const response = await apiClient.post('/telegram/sync');
        return { ...response.data, source: 'telegram' };
      }
      

      
      if (sourceFilter === 'twitter') {
        if (!isTwitterConnected) {
          throw new Error('Twitter is not connected. Connect it in Settings.');
        }
        setSyncStatus('Fetching Twitter mentions...');
        const response = await apiClient.post('/twitter/sync');
        return { ...response.data, source: 'twitter' };
      }
      if (sourceFilter === 'gmail') {
        if (!isGoogleConnected) {
          throw new Error('Gmail is not connected. Connect it in Settings.');
        }
        setSyncStatus('Fetching emails...');
        const response = await apiClient.post('/gmail/sync', { 
          max_results: 20, 
          unread_only: false,
          category: gmailCategoryFilter
        });
        return { ...response.data, source: 'gmail' };
      }

      if (sourceFilter === 'all') {
        const syncPromises = [];
        const activeSources: string[] = [];
        
        if (isGoogleConnected) {
          activeSources.push('gmail');
          syncPromises.push(
            apiClient.post('/gmail/sync', { max_results: 15, unread_only: false })
              .then(res => ({ source: 'gmail', synced: res.data.synced || 0 }))
              .catch(err => ({ source: 'gmail', error: err }))
          );
        }
        if (isTelegramConnected) {
          activeSources.push('telegram');
          syncPromises.push(
            apiClient.post('/telegram/sync')
              .then(res => ({ source: 'telegram', synced: res.data.synced || 0 }))
              .catch(err => ({ source: 'telegram', error: err }))
          );
        }

        if (isTwitterConnected) {
          activeSources.push('twitter');
          syncPromises.push(
            apiClient.post('/twitter/sync')
              .then(res => ({ source: 'twitter', synced: res.data.synced || 0 }))
              .catch(err => ({ source: 'twitter', error: err }))
          );
        }
        
        if (syncPromises.length === 0) {
          setSyncStatus('No active integrations to sync.');
          await new Promise((resolve) => setTimeout(resolve, 800));
          return { synced: 0, source: 'none' };
        }
        
        setSyncStatus(`Syncing active services (${activeSources.join(', ')})...`);
        const results = await Promise.all(syncPromises);
        
        let totalSynced = 0;
        const succeeded: string[] = [];
        for (const res of results) {
          if ('error' in res) {
            console.error(`Sync error for ${res.source}:`, res.error);
          } else {
            totalSynced += res.synced;
            succeeded.push(res.source);
          }
        }
        
        return { synced: totalSynced, source: 'all', succeeded };
      }

      return { synced: 0, source: 'none' };
    },
    onSuccess: (data) => {
      const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      if (typeof window !== 'undefined') {
        localStorage.setItem('last_synced_at', now);
      }
      setLastSyncedAt(now);

      if (data.source === 'telegram') {
        setSyncStatus({ message: `Synced ${data.synced} Telegram chat updates! (AI processing active)`, isError: false });
      } else if (data.source === 'twitter') {
        setSyncStatus({ message: `Synced ${data.synced} new Twitter mentions!`, isError: false });
      } else if (data.source === 'gmail') {
        setSyncStatus({ message: `Synced ${data.synced} new emails!`, isError: false });
      } else if (data.source === 'all') {
        setSyncStatus({ message: `Consolidated sync complete! Fetched ${data.synced} updates across connected platforms.`, isError: false });
      } else {
        setSyncStatus({ message: 'Sync completed.', isError: false });
      }
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      setTimeout(() => setSyncStatus(null), 4000);
    },
    onError: (error: any) => {
      console.error(error);
      const errorDetails = error.response?.data?.errorDetails;
      const detail = error.response?.data?.detail || 'Sync failed. Check API configurations in settings.';
      if (errorDetails) {
        setSyncStatus({
          message: errorDetails.message || detail,
          isError: true,
          action: errorDetails.action,
          actionUrl: errorDetails.action_url
        });
      } else {
        setSyncStatus({
          message: detail,
          isError: true
        });
      }
    },
    onSettled: () => {
      setSyncLoading(false);
    }
  });

  // Mark message as read
  const markReadMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.patch(`/gmail/messages/${id}/read`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      queryClient.invalidateQueries({ queryKey: ['message-detail', selectedId] });
    }
  });

  // Run AI Summary/Analysis on selected message
  const analyzeMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.post('/ai/analyze', { message_id: id });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      queryClient.invalidateQueries({ queryKey: ['message-detail', selectedId] });
    }
  });

  // Run AI on all unprocessed inbox messages
  const runInboxAiMutation = useMutation({
    mutationFn: async () => {
      setInboxAiLoading(true);
      setInboxAiStatus('Running AI...');
      const response = await apiClient.post('/ai/analyze', {});
      return response.data;
    },
    onSuccess: (data) => {
      setInboxAiStatus(`AI complete! Processed ${data.processed_count} messages.`);
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      if (selectedId) {
        queryClient.invalidateQueries({ queryKey: ['message-detail', selectedId] });
      }
      setTimeout(() => setInboxAiStatus(null), 4000);
    },
    onError: (err: any) => {
      console.error(err);
      const detail = err.response?.data?.detail || err.message;
      setInboxAiStatus(`AI processing failed: ${detail}`);
      setTimeout(() => setInboxAiStatus(null), 4500);
    },
    onSettled: () => {
      setInboxAiLoading(false);
    }
  });

  useEffect(() => {
    if (selectedMessage) {
      setReplyDraft(selectedMessage.suggested_reply || '');
    }
  }, [selectedMessage]);

  useEffect(() => {
    if (selectedIdParam) {
      setSelectedId(parseInt(selectedIdParam, 10));
    }
  }, [selectedIdParam]);

  const handleSelectMessage = (id: number) => {
    setSelectedId(id);
    router.push(`/inbox?id=${id}`);
  };

  const handleGenerateReply = async () => {
    if (!selectedId) return;
    setIsGeneratingReply(true);
    setReplySuccessMsg(null);
    try {
      const response = await apiClient.post(`/reply/message/${selectedId}`, null, {
        params: { tone, language }
      });
      setReplyDraft(response.data.reply);
      setReplySuccessMsg('AI Draft generated successfully!');
      queryClient.invalidateQueries({ queryKey: ['message-detail', selectedId] });
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to generate reply');
    } finally {
      setIsGeneratingReply(false);
    }
  };

  const handleImproveReply = async () => {
    if (!selectedMessage) return;
    setIsImproving(true);
    try {
      const response = await apiClient.post('/reply/improve', {
        original_email: selectedMessage.body,
        reply_draft: replyDraft
      });
      setReplyDraft(response.data.reply);
      setReplySuccessMsg('AI Draft polished successfully!');
    } catch (err: any) {
      console.error(err);
    } finally {
      setIsImproving(false);
    }
  };

  const handleCopyReply = () => {
    navigator.clipboard.writeText(replyDraft);
    setReplySuccessMsg('Copied to clipboard!');
    setTimeout(() => setReplySuccessMsg(null), 3000);
  };

  const handleApproveReply = async () => {
    if (!selectedId) return;
    setIsApproving(true);
    setReplySuccessMsg(null);
    try {
      await apiClient.post(`/reply/message/${selectedId}/approve`, {
        reply_text: replyDraft
      });
      setReplySuccessMsg('Draft approved and sent successfully!');
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      queryClient.invalidateQueries({ queryKey: ['message-detail', selectedId] });
      setTimeout(() => setReplySuccessMsg(null), 4000);
    } catch (err: any) {
      console.error(err);
      const detail = err.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : (detail?.message || 'Failed to dispatch reply. Check credentials.');
      alert(message);
    } finally {
      setIsApproving(false);
    }
  };

  const handleMarkRead = () => {
    if (selectedId) {
      markReadMutation.mutate(selectedId);
    }
  };

  const handleAnalyze = () => {
    if (selectedId) {
      analyzeMutation.mutate(selectedId);
    }
  };
  // Filter messages
  const filteredMessages = messages?.filter((msg: any) => {
    const query = searchQuery.toLowerCase();
    const matchQuery = 
      (msg.sender?.toLowerCase() || '').includes(query) ||
      (msg.subject?.toLowerCase() || '').includes(query) ||
      (msg.body?.toLowerCase() || '').includes(query);
    if (!matchQuery) return false;


    return true;
  }) || [];

  const groupedMessages = React.useMemo(() => {
    const threadsMap = new Map<string, any>();
    const result: any[] = [];

    for (const msg of filteredMessages) {
      if (msg.thread_id) {
        if (!threadsMap.has(msg.thread_id)) {
          threadsMap.set(msg.thread_id, msg);
          result.push(msg);
        } else {
          const existing = threadsMap.get(msg.thread_id);
          if (new Date(msg.received_at) > new Date(existing.received_at)) {
            const idx = result.indexOf(existing);
            if (idx !== -1) {
              result[idx] = msg;
            }
            threadsMap.set(msg.thread_id, msg);
          }
        }
      } else {
        result.push(msg);
      }
    }
    return result;
  }, [filteredMessages]);

  const threadMessages = React.useMemo(() => {
    if (!selectedMessage?.thread_id || !messages) return [];
    return messages
      .filter((m: any) => m.thread_id === selectedMessage.thread_id)
      .sort((a: any, b: any) => new Date(a.received_at).getTime() - new Date(b.received_at).getTime());
  }, [selectedMessage, messages]);
  // Parse action items string if present (represented as array in text)
  const parseActionItems = (actionItemsStr: string | null) => {
    if (!actionItemsStr) return [];
    try {
      const jsonStr = actionItemsStr.replace(/'/g, '"');
      return JSON.parse(jsonStr);
    } catch (e) {
      return actionItemsStr.split(/[\n,]+/).map(item => item.trim().replace(/^-\s*/, '')).filter(Boolean);
    }
  };

  return (
    <SidebarLayout>
      <div className="flex h-full w-full overflow-hidden bg-transparent relative z-10">
        
        {/* Left Pane: Message List */}
        <div className={`w-full md:w-96 flex flex-col border-r border-zinc-900/60 h-full overflow-hidden bg-zinc-950/20 backdrop-blur-md ${selectedId ? 'hidden md:flex' : 'flex'}`}>
          {/* Header & Sync */}
          <div className="p-4 border-b border-zinc-900/60 space-y-3 bg-zinc-950/40 backdrop-blur-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Inbox className="w-4 h-4 text-indigo-400" />
                <div className="flex flex-col">
                  <h1 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Executive Inbox</h1>
                  {lastSyncedAt && (
                    <p className="text-[10px] text-zinc-500 font-medium">Last synced: {lastSyncedAt}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => syncMutation.mutate()}
                  disabled={syncLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-zinc-100 text-zinc-950 hover:bg-zinc-200 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 shadow-md shadow-zinc-950/25 shrink-0"
                >
                  {syncLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  {syncLoading ? 'Syncing...' : 'Sync'}
                </button>
                <button 
                  onClick={() => runInboxAiMutation.mutate()}
                  disabled={inboxAiLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-650 hover:bg-indigo-600 text-zinc-100 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 shadow-md shadow-indigo-950/25 border border-indigo-500/30 shrink-0"
                >
                  {inboxAiLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-400" />}
                  {inboxAiLoading ? 'Running AI...' : 'Run AI'}
                </button>
              </div>
            </div>

            {syncStatus && (
              <div className={`text-xs px-3.5 py-2.5 rounded-lg border flex items-center justify-between gap-3 ${
                (typeof syncStatus === 'object' && syncStatus.isError) || (typeof syncStatus === 'string' && syncStatus.startsWith('Error'))
                  ? 'border-red-900/30 bg-red-950/20 text-red-400' 
                  : 'border-zinc-800 bg-zinc-900/40 text-zinc-300'
              }`}>
                <span>
                  {typeof syncStatus === 'string' ? syncStatus : syncStatus.message}
                </span>
                {typeof syncStatus === 'object' && syncStatus.action === 'reconnect' && (
                  <Link 
                    href="/settings" 
                    className="shrink-0 px-2 py-0.5 bg-red-950 border border-red-900/40 hover:border-red-800 hover:bg-red-900 hover:text-white rounded text-[10px] font-semibold transition-all cursor-pointer"
                  >
                    Reconnect
                  </Link>
                )}
                {typeof syncStatus === 'object' && syncStatus.action === 'enable_api' && syncStatus.actionUrl && (
                  <a 
                    href={syncStatus.actionUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="shrink-0 px-2 py-0.5 bg-red-950 border border-red-900/40 hover:border-red-800 hover:bg-red-900 hover:text-white rounded text-[10px] font-semibold transition-all cursor-pointer"
                  >
                    Enable API
                  </a>
                )}
              </div>
            )}

            {inboxAiStatus && (
              <div className={`text-xs px-3.5 py-2.5 rounded-lg border ${
                inboxAiStatus.includes('failed')
                  ? 'border-red-900/30 bg-red-950/20 text-red-400' 
                  : 'border-zinc-800 bg-zinc-900/40 text-zinc-300'
              }`}>
                <span>{inboxAiStatus}</span>
              </div>
            )}

            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
              <input
                type="text"
                placeholder="Search communications..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-900/40 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-indigo-500/50 transition-all duration-300"
              />
            </div>

            {/* Filters */}
            <div className="flex gap-2 text-xs">
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="bg-zinc-900/40 border border-zinc-800 rounded-lg px-2.5 py-1 text-zinc-400 focus:text-zinc-100 outline-none cursor-pointer hover:border-zinc-700/80 transition-colors"
              >
                <option value="all">All Sources</option>
                <option value="gmail">Gmail</option>
                <option value="twitter">Twitter</option>
                <option value="telegram">Telegram</option>
              </select>
              <select
                value={gmailCategoryFilter}
                onChange={(e) => setGmailCategoryFilter(e.target.value)}
                className="bg-zinc-900/40 border border-zinc-800 rounded-lg px-2.5 py-1 text-zinc-400 focus:text-zinc-100 outline-none cursor-pointer hover:border-zinc-700/80 transition-colors"
              >
                <option value="all">All</option>
                <option value="primary">Primary</option>
                <option value="promotions">Promotions</option>
                <option value="social">Social</option>
                <option value="updates">Updates</option>
              </select>


              <button 
                onClick={() => setUnreadOnly(!unreadOnly)}
                className={`px-2.5 py-1 rounded-lg border transition-all duration-300 cursor-pointer ${
                  unreadOnly 
                    ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-400' 
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 hover:border-zinc-750'
                }`}
              >
                Unread Only
              </button>
            </div>
          </div>

          {/* List Items */}
          <div className="flex-1 overflow-y-auto divide-y divide-zinc-900/60 bg-transparent">
            {isMessagesLoading ? (
              <div className="py-16 flex justify-center text-zinc-500">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              </div>
            ) : groupedMessages.length > 0 ? (
              groupedMessages.map((msg: any) => {
                const isSelected = selectedId === msg.id;
                return (
                  <div
                    key={msg.id}
                    onClick={() => handleSelectMessage(msg.id)}
                    className={`p-4 cursor-pointer transition-all duration-300 hover:bg-zinc-900/30 flex flex-col gap-2 relative border-b border-zinc-900/50 ${
                      isSelected ? 'bg-zinc-900/50 border-l-2 border-indigo-500 shadow-sm shadow-indigo-550/5' : ''
                    }`}
                  >
                    {msg.status === 'unread' && !isSelected && (
                      <span className="absolute top-4 right-4 h-2 w-2 rounded-full bg-indigo-500 shadow-sm shadow-indigo-400 animate-pulse"></span>
                    )}

                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-zinc-400 truncate max-w-[180px]">
                        {msg.sender}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-550">
                        {msg.received_at ? new Date(msg.received_at).toLocaleDateString() : ''}
                      </span>
                    </div>

                    <p className="text-xs font-bold text-zinc-200 truncate">
                      {msg.subject || (
                        msg.source === 'whatsapp' ? 'WhatsApp Direct Message' :
                        msg.source === 'twitter' ? 'Twitter Mention' :
                        msg.source === 'telegram' ? 'Telegram Message' :
                        msg.source === 'discord' ? 'Discord Message' :
                        '(no subject)'
                      )}
                    </p>

                    <p className="text-xs text-zinc-405 line-clamp-2">
                      {msg.summary || sanitizeEmailBody(msg.body)}
                    </p>

                    <div className="flex items-center gap-1.5 mt-1.5">
                      <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                        msg.source === 'gmail' ? 'bg-red-950/20 text-red-400 border border-red-900/20' :
                        msg.source === 'whatsapp' ? 'bg-green-950/20 text-green-400 border border-green-900/20' :
                        msg.source === 'twitter' ? 'bg-zinc-900 border border-zinc-800 text-zinc-300' :
                        msg.source === 'telegram' ? 'bg-sky-950/20 text-sky-400 border border-sky-900/20' :
                        msg.source === 'discord' ? 'bg-indigo-950/20 text-indigo-400 border border-indigo-900/20' :
                        'bg-zinc-900 border border-zinc-800 text-zinc-400'
                      }`}>
                        {msg.source}
                      </span>

                      {msg.source === 'gmail' && msg.category && (
                        <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                          msg.category === 'primary' ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/20' :
                          msg.category === 'promotions' ? 'bg-purple-950/20 text-purple-400 border border-purple-900/20' :
                          msg.category === 'social' ? 'bg-pink-950/20 text-pink-400 border border-pink-900/20' :
                          msg.category === 'updates' ? 'bg-blue-950/20 text-blue-400 border border-blue-900/20' :
                          'bg-zinc-900 border border-zinc-800 text-zinc-400'
                        }`}>
                          {msg.category}
                        </span>
                      )}

                      {msg.source === 'discord' && msg.subject && (
                        <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border border-indigo-900/20 bg-indigo-950/20 text-indigo-400 font-semibold">
                          {msg.subject.startsWith('Server:') ? 'Server Message' : 'Personal DM'}
                        </span>
                      )}

                      {msg.priority && (
                        <span className={`text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-semibold ${
                          msg.priority === 'critical' ? 'bg-rose-950/20 text-rose-450 border border-rose-900/20' :
                          msg.priority === 'high' ? 'bg-amber-950/20 text-amber-450 border border-amber-900/20' :
                          'bg-zinc-900 border border-zinc-800 text-zinc-500'
                        }`}>
                          {msg.priority}
                        </span>
                      )}

                      {msg.requires_reply && (
                        <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-indigo-950/20 text-indigo-400 border border-indigo-900/20 font-semibold">
                          Reply Needed
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            ) : !hasConnections ? (
              <div className="p-8 text-center text-zinc-400 text-xs flex flex-col items-center justify-center gap-3 py-16">
                <ShieldAlert className="w-8 h-8 text-zinc-650 animate-pulse" />
                <p className="font-semibold text-zinc-300">No accounts connected</p>
                <p className="text-zinc-550 max-w-[200px] leading-relaxed mx-auto">
                  Connect Google (Gmail) or other channels in Settings to start viewing and orchestrating messages.
                </p>
                <Link 
                  href="/settings"
                  className="mt-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-[10px] font-semibold text-zinc-200 hover:text-zinc-50 rounded-lg transition-all cursor-pointer"
                >
                  Go to Settings
                </Link>
              </div>
            ) : (
              <div className="p-12 text-center text-zinc-600 italic text-xs">
                No communications found matching the criteria.
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Message Detail */}
        <div className={`flex-1 flex flex-col h-full overflow-hidden bg-transparent ${!selectedId ? 'hidden md:flex' : 'flex'}`}>
          {selectedId ? (
            isDetailLoading ? (
              <div className="flex-1 flex items-center justify-center text-zinc-500">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              </div>
            ) : selectedMessage ? (
              <div className="flex-1 flex flex-col h-full overflow-hidden bg-transparent">
                {/* Header Actions */}
                <div className="p-4 border-b border-zinc-900/60 flex items-center justify-between bg-zinc-950/30 backdrop-blur-md">
                  <button 
                    onClick={() => {
                      setSelectedId(null);
                      router.push('/inbox');
                    }}
                    className="md:hidden flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-100"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back
                  </button>

                  <div className="flex items-center gap-2.5 ml-auto">
                    <button 
                      onClick={handleAnalyze}
                      disabled={analyzeMutation.isPending}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 hover:border-zinc-750 text-zinc-300 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {analyzeMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-400" />}
                      {analyzeMutation.isPending ? 'Running AI...' : 'Run AI'}
                    </button>
                    {selectedMessage.status === 'unread' && (
                      <button 
                        onClick={handleMarkRead}
                        className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 hover:border-zinc-750 text-zinc-300 transition-all cursor-pointer"
                      >
                        <Check className="w-3.5 h-3.5 text-emerald-450" />
                        Mark Read
                      </button>
                    )}
                  </div>
                </div>

                {/* Content Pane */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-transparent">
                  {/* Metadata Card */}
                  <div className="glass-panel rounded-xl p-5 space-y-4">
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-550">
                          {selectedMessage.thread_id ? "Chat / Group Title" : "Sender"}
                        </span>
                        <h2 className="text-base font-bold text-zinc-100 mt-1">{selectedMessage.sender}</h2>
                        {selectedMessage.recipient && selectedMessage.recipient !== selectedMessage.sender && (
                          <p className="text-[10px] text-zinc-500 mt-1">
                            {selectedMessage.source === 'telegram' ? 'Sender' : 'To'}: {selectedMessage.recipient}
                          </p>
                        )}                      </div>
                      <div className="text-right">
                        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-555">Received</span>
                        <p className="text-xs text-zinc-400 mt-1">
                          {selectedMessage.received_at ? new Date(selectedMessage.received_at).toLocaleString() : ''}
                        </p>
                      </div>
                    </div>

                    {selectedMessage.source === 'gmail' ? (
                      <div className="pt-3.5 border-t border-zinc-900/60">
                        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-550">Subject</span>
                        <h3 className="text-base font-bold text-zinc-100 mt-1">{selectedMessage.subject || '(no subject)'}</h3>
                      </div>
                    ) : (
                      <div className="pt-3.5 border-t border-zinc-900/60">
                        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-550">Integration Channel</span>
                        <h3 className="text-sm font-semibold text-indigo-400 mt-1">
                          {selectedMessage.source === 'whatsapp' ? 'WhatsApp Direct Message' :
                           selectedMessage.source === 'telegram' ? 'Telegram' :
                           selectedMessage.source === 'discord' ? 'Discord' : 'Twitter Mention'}
                        </h3>
                      </div>
                    )}
                  </div>

                  {/* AI Summarization & Sentiment (If Processed) */}
                  {selectedMessage.is_processed && (selectedMessage.summary || selectedMessage.sentiment) ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* Summary */}
                      <div className="md:col-span-2 bg-gradient-to-b from-indigo-500/5 to-transparent border border-zinc-900/60 backdrop-blur-md rounded-xl p-5 space-y-2">
                        <h4 className="text-xs font-semibold text-indigo-400 uppercase tracking-widest flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> AI Summary {selectedMessage.thread_id ? "(Selected Message)" : "Executive Summary"}
                        </h4>
                        <p className="text-xs text-zinc-300 leading-relaxed font-normal">
                          {selectedMessage.summary}
                        </p>
                      </div>

                      {/* Sentiment & Metadata */}
                      <div className="glass-panel rounded-xl p-5 space-y-4">
                        <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">Metadata Tags {selectedMessage.thread_id ? "(Selected)" : ""}</h4>
                        
                        <div>
                          <p className="text-[10px] font-mono text-zinc-550">Sentiment</p>
                          <span className="inline-flex items-center gap-1.5 mt-1 text-xs font-semibold text-zinc-300 capitalize">
                            <Smile className="w-3.5 h-3.5 text-indigo-400" />
                            {selectedMessage.sentiment || 'Neutral'}
                          </span>
                        </div>

                        {selectedMessage.category && (
                          <div>
                            <p className="text-[10px] font-mono text-zinc-550">Category</p>
                            <span className="inline-block mt-1 text-xs text-zinc-300 bg-zinc-900/60 px-2.5 py-0.5 rounded border border-zinc-800 font-semibold">
                              {selectedMessage.category}
                            </span>
                          </div>
                        )}

                        {selectedMessage.confidence_score !== undefined && (
                          <div>
                            <p className="text-[10px] font-mono text-zinc-550">AI Score</p>
                            <div className="w-full bg-zinc-950 rounded-full h-1.5 mt-2 border border-zinc-850">
                              <div 
                                className="bg-indigo-500 h-full rounded-full shadow-sm shadow-indigo-400" 
                                style={{ width: `${selectedMessage.confidence_score || 50}%` }}
                              ></div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* Action Items List */}
                  {selectedMessage.action_items && (
                    <div className="glass-panel rounded-xl p-5 space-y-3.5">
                      <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-widest flex items-center gap-1.5">
                        <CheckSquare className="w-3.5 h-3.5" /> Extracted Action Items
                      </h4>
                      <ul className="space-y-2">
                        {parseActionItems(selectedMessage.action_items).map((item: string, idx: number) => (
                          <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-300">
                            <input 
                              type="checkbox" 
                              className="mt-0.5 accent-indigo-500 rounded border-zinc-800 bg-zinc-950 w-3.5 h-3.5 focus:ring-0" 
                            />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Raw Message Body or Thread Conversation */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">
                      {selectedMessage.thread_id ? "Conversation History" : "Original Correspondence"}
                    </h4>
                    {selectedMessage.thread_id && threadMessages.length > 0 ? (
                      <div className="space-y-2">
                        {threadMessages.length > 1 && (
                          <p className="text-[10px] text-zinc-500 italic px-1">
                            💡 Tip: Click any message bubble below to select it for AI analysis and smart replies.
                          </p>
                        )}
                        <div className="glass-panel rounded-xl p-5 space-y-4 max-h-[500px] overflow-y-auto flex flex-col gap-3">
                          {threadMessages.map((tmsg: any) => {
                            const isCurrent = tmsg.id === selectedMessage.id;
                            return (
                              <div 
                                key={tmsg.id} 
                                onClick={() => handleSelectMessage(tmsg.id)}
                                className={`flex flex-col max-w-[85%] rounded-2xl p-4 space-y-1.5 self-start transition-all duration-300 ${
                                  isCurrent
                                    ? 'bg-indigo-500/10 border border-indigo-500/35 shadow-sm shadow-indigo-500/5'
                                    : 'bg-zinc-900/30 border border-zinc-800/40 hover:bg-zinc-900/50 hover:border-zinc-700/60 cursor-pointer shadow-sm hover:shadow-indigo-500/2'
                                }`}
                              >
                                <div className="flex items-center justify-between gap-6 text-[10px] font-semibold text-zinc-400">
                                  <span className="truncate max-w-[150px]">{tmsg.recipient || tmsg.sender}</span>
                                  <span className="font-mono text-zinc-500">
                                    {tmsg.received_at ? new Date(tmsg.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                  </span>
                                </div>
                                <div className="text-xs text-zinc-200 leading-relaxed break-words font-sans font-normal">
                                  {tmsg.html_body ? (
                                    <div 
                                      className="prose prose-invert max-w-none text-zinc-200"
                                      style={{ color: 'inherit' }}
                                      dangerouslySetInnerHTML={{ __html: typeof window !== 'undefined' ? DOMPurify.sanitize(tmsg.html_body) : tmsg.html_body }}
                                    />
                                  ) : (
                                    <p className="whitespace-pre-wrap">{sanitizeEmailBody(tmsg.body)}</p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="glass-panel rounded-xl p-5 text-sm text-zinc-300 font-normal leading-relaxed font-sans overflow-x-auto">
                        {selectedMessage.html_body ? (
                          <div 
                            className="prose prose-invert max-w-none text-zinc-300"
                            style={{ color: 'inherit' }}
                            dangerouslySetInnerHTML={{ __html: typeof window !== 'undefined' ? DOMPurify.sanitize(selectedMessage.html_body) : selectedMessage.html_body }}
                          />
                        ) : (
                          <div className="whitespace-pre-wrap break-words">{sanitizeEmailBody(selectedMessage.body)}</div>
                        )}
                      </div>
                    )}                  </div>

                  {/* Suggested Smart Reply Module */}
                  <div className="glass-panel rounded-xl p-5 space-y-4 relative overflow-hidden group/reply hover:border-indigo-500/20 transition-all duration-500">
                    <div className="absolute -top-12 -right-12 w-48 h-48 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none group-hover/reply:bg-indigo-500/10 transition-all duration-500"></div>

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-900/60 pb-3.5 relative z-10">
                      <h4 className="text-xs font-semibold text-indigo-400 uppercase tracking-widest flex items-center gap-1.5">
                        <MessageSquare className="w-3.5 h-3.5" /> Smart Copilot Draft
                      </h4>
                      
                      {/* Generation Settings */}
                      <div className="flex items-center gap-2 flex-wrap text-xs">
                        {/* Tone Selector */}
                        <div className="flex items-center gap-1.5 bg-zinc-950/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 hover:border-zinc-700/80 transition-colors">
                          <Smile className="w-3.5 h-3.5 text-zinc-500" />
                          <select 
                            value={tone} 
                            onChange={(e) => setTone(e.target.value)} 
                            className="bg-transparent text-zinc-350 outline-none border-none cursor-pointer font-semibold text-[11px]"
                          >
                            <option value="professional">Professional</option>
                            <option value="friendly">Friendly</option>
                            <option value="direct">Direct</option>
                            <option value="diplomatic">Diplomatic</option>
                          </select>
                        </div>

                        {/* Language Selector */}
                        <div className="flex items-center gap-1.5 bg-zinc-950/60 border border-zinc-800 rounded-lg px-2.5 py-1.5 hover:border-zinc-700/80 transition-colors">
                          <Globe className="w-3.5 h-3.5 text-zinc-500" />
                          <select 
                            value={language} 
                            onChange={(e) => setLanguage(e.target.value)} 
                            className="bg-transparent text-zinc-350 outline-none border-none cursor-pointer font-semibold text-[11px]"
                          >
                            <option value="English">English</option>
                            <option value="Spanish">Spanish</option>
                            <option value="French">French</option>
                            <option value="German">German</option>
                          </select>
                        </div>

                        <button 
                          onClick={handleGenerateReply}
                          disabled={isGeneratingReply}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-100 text-zinc-950 hover:bg-zinc-200 text-xs font-semibold rounded-lg transition-all cursor-pointer disabled:opacity-50"
                        >
                          {isGeneratingReply ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                          Draft
                        </button>
                      </div>
                    </div>

                    {replySuccessMsg && (
                      <div className="text-xs px-3 py-2 rounded-lg border border-emerald-900/30 bg-emerald-950/20 text-emerald-400 relative z-10">
                        {replySuccessMsg}
                      </div>
                    )}

                    {/* Draft Text Area */}
                    <div className="space-y-3.5 relative z-10">
                      <textarea
                        value={replyDraft}
                        onChange={(e) => setReplyDraft(e.target.value)}
                        placeholder="Smart Draft will appear here once generated. Or you can type custom text directly."
                        rows={6}
                        className="w-full bg-zinc-950/60 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-200 placeholder-zinc-600 focus:border-indigo-500/50 outline-none leading-relaxed resize-none transition-all duration-300"
                      />

                      <div className="flex items-center gap-2">
                        <button 
                          onClick={handleCopyReply}
                          disabled={!replyDraft}
                          className="flex items-center justify-center gap-1.5 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-350 transition-all cursor-pointer disabled:opacity-40"
                        >
                          <Copy className="w-3.5 h-3.5 text-zinc-400" />
                          Copy Draft
                        </button>
                        
                        <button 
                          onClick={handleImproveReply}
                          disabled={isImproving || !replyDraft}
                          className="flex items-center justify-center gap-1.5 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-350 transition-all cursor-pointer disabled:opacity-40"
                        >
                          {isImproving ? <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-455" />}
                          AI Polish Draft
                        </button>

                        <button 
                          onClick={handleApproveReply}
                          disabled={isApproving || !replyDraft}
                          className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-all cursor-pointer disabled:opacity-50 ml-auto active:scale-[0.98]"
                        >
                          {isApproving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                          Approve & Send
                        </button>
                      </div>
                    </div>
                  </div>

                </div>

              </div>
            ) : null
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-transparent">
              <Inbox className="w-12 h-12 text-zinc-800 mb-3 animate-pulse" />
              <h3 className="text-sm font-semibold text-zinc-300">Select a Communication</h3>
              <p className="text-xs text-zinc-550 mt-1 max-w-xs leading-relaxed">
                Select an item from the inbox pane to analyze context, read summaries, and draft quick replies.
              </p>
            </div>
          )}
        </div>

      </div>

      {notification && (
        <div 
          onClick={() => handleSelectMessage(notification.id)}
          className="fixed bottom-6 right-6 z-50 max-w-sm w-full bg-zinc-950/95 border-2 border-amber-500/50 rounded-xl shadow-2xl p-4 animate-in slide-in-from-bottom duration-300 backdrop-blur-md cursor-pointer hover:border-amber-450 transition-all"
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
        </div>
      )}
    </SidebarLayout>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-950 relative overflow-hidden">
        <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
        <p className="text-xs font-mono text-zinc-500 tracking-widest uppercase animate-pulse">Loading Inbox...</p>
      </div>
    }>
      <InboxContent />
    </Suspense>
  );
}
