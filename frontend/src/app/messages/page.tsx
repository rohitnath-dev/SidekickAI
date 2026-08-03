'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  MessageSquare, 
  Send, 
  User, 
  Phone, 
  Sparkles, 
  MessageCircle, 
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Loader2,
  ListFilter
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

const TwitterIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

export default function MessagesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'whatsapp' | 'twitter'>('whatsapp');

  // ---------------------------------------------------------------------------
  // WhatsApp States & API Mutators
  // ---------------------------------------------------------------------------
  const [waTo, setWaTo] = useState('');
  const [waText, setWaText] = useState('');
  const [waMsgStatus, setWaMsgStatus] = useState<string | null>(null);
  const [waMsgError, setWaMsgError] = useState<string | null>(null);
  const [waSending, setWaSending] = useState(false);
  const [selectedWaMsgId, setSelectedWaMsgId] = useState<number | null>(null);

  // WhatsApp AI Assist States
  const [waAssistSender, setWaAssistSender] = useState('');
  const [waAssistContent, setWaAssistContent] = useState('');
  const [waAssistReply, setWaAssistReply] = useState('');
  const [waAssistLoading, setWaAssistLoading] = useState(false);

  // Fetch WhatsApp Messages Query
  const { data: waMessages, isLoading: isWaLoading, refetch: refetchWaMessages } = useQuery({
    queryKey: ['wa-messages'],
    queryFn: async () => {
      const response = await apiClient.get('/whatsapp/messages');
      return response.data;
    },
    refetchInterval: 30000,
  });

  const sendWhatsAppMutation = useMutation({
    mutationFn: async () => {
      setWaSending(true);
      setWaMsgStatus(null);
      setWaMsgError(null);
      const response = await apiClient.post('/whatsapp/send', {
        to: waTo,
        text: waText,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setWaMsgStatus(`Message successfully sent! (ID: ${data.message_id || 'N/A'})`);
      setWaText('');
    },
    onError: (err: any) => {
      console.error(err);
      setWaMsgError(err.response?.data?.detail || 'Failed to send WhatsApp message. Ensure WhatsApp credentials are set.');
    },
    onSettled: () => {
      setWaSending(false);
    }
  });

  const generateWaReplyMutation = useMutation({
    mutationFn: async () => {
      setWaAssistLoading(true);
      const response = await apiClient.post('/whatsapp/reply/generate', {
        sender_name: waAssistSender,
        message_content: waAssistContent,
        to: waTo,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setWaAssistReply(data.reply_text);
    },
    onError: (err: any) => {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to generate AI reply');
    },
    onSettled: () => {
      setWaAssistLoading(false);
    }
  });

  const sendWaReplyMutation = useMutation({
    mutationFn: async () => {
      setWaSending(true);
      setWaMsgStatus(null);
      setWaMsgError(null);
      const response = await apiClient.post('/whatsapp/reply/send', {
        sender_name: waAssistSender,
        message_content: waAssistContent,
        to: waTo,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setWaMsgStatus(`AI reply sent! (Draft: "${data.reply_text.substring(0, 40)}...")`);
      setWaAssistReply(data.reply_text);
    },
    onError: (err: any) => {
      console.error(err);
      setWaMsgError(err.response?.data?.detail || 'Failed to send AI reply.');
    },
    onSettled: () => {
      setWaSending(false);
    }
  });

  // ---------------------------------------------------------------------------
  // Twitter/X States & API Mutators
  // ---------------------------------------------------------------------------
  const [twitterUserId, setTwitterUserId] = useState('');
  const [tweetType, setTweetType] = useState<'mentions' | 'timeline'>('mentions');
  
  // Selected Tweet state for generating/posting replies
  const [selectedTweet, setSelectedTweet] = useState<any | null>(null);
  const [twitterReplyText, setTwitterReplyText] = useState('');
  const [isGeneratingTwitterReply, setIsGeneratingTwitterReply] = useState(false);
  const [isPostingTwitterReply, setIsPostingTwitterReply] = useState(false);
  const [twitterStatus, setTwitterStatus] = useState<string | null>(null);
  const [twitterError, setTwitterError] = useState<string | null>(null);

  // Fetch Tweets Query
  const { data: tweets, isLoading: isTweetsLoading, error: tweetsError, refetch: refetchTweets } = useQuery({
    queryKey: ['tweets', twitterUserId, tweetType],
    queryFn: async () => {
      if (!twitterUserId) return [];
      const endpoint = tweetType === 'mentions' ? '/twitter/mentions' : '/twitter/timeline';
      const response = await apiClient.get(endpoint, {
        params: { user_id: twitterUserId, max_results: 10 }
      });
      return response.data;
    },
    enabled: !!twitterUserId,
    retry: false,
  });

  const generateTwitterReply = async (tweet: any) => {
    setIsGeneratingTwitterReply(true);
    setTwitterStatus(null);
    setTwitterError(null);
    try {
      const response = await apiClient.post('/twitter/reply/generate', {
        tweet_id: tweet.id,
        post_content: tweet.text,
        author_handle: tweet.author_id || 'unknown',
      });
      setTwitterReplyText(response.data.reply_text);
    } catch (err: any) {
      console.error(err);
      setTwitterError(err.response?.data?.detail || 'Failed to generate Twitter reply.');
    } finally {
      setIsGeneratingTwitterReply(false);
    }
  };

  const postTwitterReply = async () => {
    if (!selectedTweet) return;
    setIsPostingTwitterReply(true);
    setTwitterStatus(null);
    setTwitterError(null);
    try {
      const response = await apiClient.post('/twitter/reply/post', {
        tweet_id: selectedTweet.id,
        post_content: selectedTweet.text,
        author_handle: selectedTweet.author_id || 'unknown',
      });
      setTwitterStatus('Reply posted to Twitter successfully!');
      setTwitterReplyText(response.data.reply_text);
    } catch (err: any) {
      console.error(err);
      setTwitterError(err.response?.data?.detail || 'Failed to post reply. Ensure Twitter write credentials are set.');
    } finally {
      setIsPostingTwitterReply(false);
    }
  };

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto h-full overflow-y-auto">
        {/* Title */}
        <div className="border-b border-zinc-900 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Direct Messaging Hub</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Automate conversation replies and manage direct integrations across WhatsApp Business and Twitter/X.
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex border-b border-zinc-900 gap-6 text-sm font-semibold select-none">
          <button
            onClick={() => setActiveTab('whatsapp')}
            className={`pb-3 transition-all cursor-pointer flex items-center gap-2 relative ${
              activeTab === 'whatsapp' ? 'text-zinc-50 border-b-2 border-indigo-500' : 'text-zinc-450 hover:text-zinc-200'
            }`}
          >
            <MessageCircle className="w-4 h-4" />
            WhatsApp Business Portal
          </button>
          <button
            onClick={() => setActiveTab('twitter')}
            className={`pb-3 transition-all cursor-pointer flex items-center gap-2 relative ${
              activeTab === 'twitter' ? 'text-zinc-50 border-b-2 border-indigo-500' : 'text-zinc-450 hover:text-zinc-200'
            }`}
          >
            <TwitterIcon className="w-4 h-4" />
            Twitter / X Desk
          </button>
        </div>

        {/* Tab 1: WhatsApp Portal */}
        {activeTab === 'whatsapp' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Column 1: Incoming WhatsApp Feed */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <div className="flex items-center gap-2">
                  <MessageCircle className="w-4 h-4 text-zinc-400" />
                  <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Incoming Customer Chats</h2>
                </div>
                <button
                  onClick={() => refetchWaMessages()}
                  disabled={isWaLoading}
                  className="p-1.5 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-zinc-50 transition-all cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isWaLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                {isWaLoading ? (
                  <div className="py-12 flex justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
                  </div>
                ) : waMessages && waMessages.length > 0 ? (
                  <div className="divide-y divide-zinc-900">
                    {waMessages.map((msg: any) => {
                      const isSelected = selectedWaMsgId === msg.id;
                      return (
                        <div
                          key={msg.id}
                          onClick={() => {
                            setSelectedWaMsgId(msg.id);
                            setWaTo(msg.sender);
                            setWaAssistSender(msg.sender);
                            setWaAssistContent(msg.body);
                            setWaAssistReply(msg.suggested_reply || '');
                          }}
                          className={`p-3.5 cursor-pointer hover:bg-zinc-900/40 border border-transparent rounded-xl transition-all flex flex-col gap-1.5 mt-1.5 ${
                            isSelected ? 'bg-zinc-900/50 border-zinc-800 shadow-sm' : ''
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-zinc-200 truncate max-w-[130px]">
                              {msg.sender}
                            </span>
                            <span className="text-[9px] font-mono text-zinc-500 shrink-0">
                              {msg.received_at ? new Date(msg.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                          </div>
                          
                          <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                            {msg.body}
                          </p>

                          <div className="flex items-center gap-1.5 mt-1">
                            {msg.priority && (
                              <span className={`text-[8px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border font-bold ${
                                msg.priority === 'critical' ? 'bg-rose-950/20 text-rose-450 border border-rose-900/20' :
                                msg.priority === 'high' ? 'bg-amber-950/20 text-amber-455 border border-amber-900/20' :
                                'bg-zinc-950 border border-zinc-850 text-zinc-500'
                              }`}>
                                {msg.priority}
                              </span>
                            )}
                            {msg.sentiment && (
                              <span className="text-[8px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-zinc-955 border border-zinc-850 text-zinc-400">
                                {msg.sentiment}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-12 text-center text-zinc-500 italic text-xs">
                    No WhatsApp Business messages found.
                  </div>
                )}
              </div>
            </div>

            {/* Column 2: Direct Send Form */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Send className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Send Direct Message</h2>
              </div>

              {waMsgStatus && (
                <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/20 p-4 text-xs text-emerald-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                  <span>{waMsgStatus}</span>
                </div>
              )}

              {waMsgError && (
                <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-xs text-red-400">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
                  <span>{waMsgError}</span>
                </div>
              )}

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Recipient Phone Number (E.164)
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="15551234567"
                      value={waTo}
                      onChange={(e) => setWaTo(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-lg pl-10 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Message Content
                  </label>
                  <textarea
                    placeholder="Type your WhatsApp Business message..."
                    value={waText}
                    onChange={(e) => setWaText(e.target.value)}
                    rows={4}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-3 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all resize-none"
                  />
                </div>

                <button
                  onClick={() => sendWhatsAppMutation.mutate()}
                  disabled={waSending || !waTo || !waText}
                  className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                >
                  {waSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Send WhatsApp Business Message
                </button>
              </div>
            </div>

            {/* Column 3: AI Assistant Copilot */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Sparkles className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">AI Copilot Reply Drafter</h2>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Sender Name / Number
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="Jane"
                      value={waAssistSender}
                      onChange={(e) => setWaAssistSender(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-lg pl-10 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Received Message Content
                  </label>
                  <textarea
                    placeholder="Paste or click a message to load content..."
                    value={waAssistContent}
                    onChange={(e) => setWaAssistContent(e.target.value)}
                    rows={3}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-3 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => generateWaReplyMutation.mutate()}
                    disabled={waAssistLoading || !waAssistSender || !waAssistContent}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-xs font-semibold text-zinc-300 border border-zinc-800 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {waAssistLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-zinc-500" />}
                    Draft AI Reply
                  </button>

                  <button
                    onClick={() => sendWaReplyMutation.mutate()}
                    disabled={waSending || !waTo || !waAssistSender || !waAssistContent}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {waSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    Send Instantly
                  </button>
                </div>

                {waAssistReply && (
                  <div className="space-y-2 pt-3 border-t border-zinc-900">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-550">
                      Suggested AI Reply Draft
                    </label>
                    <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-4 text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">
                      {waAssistReply}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Twitter/X Desk */}
        {activeTab === 'twitter' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Feed controls & listing */}
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
                
                {/* Configuration bar */}
                <div className="flex flex-col sm:flex-row items-end gap-4 border-b border-zinc-900 pb-4">
                  <div className="space-y-2 flex-1 w-full">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      Twitter User ID (Numerical)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. 12345678"
                      value={twitterUserId}
                      onChange={(e) => setTwitterUserId(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                    />
                  </div>

                  <div className="flex items-center gap-2 text-xs w-full sm:w-auto">
                    <select
                      value={tweetType}
                      onChange={(e) => setTweetType(e.target.value as any)}
                      className="bg-zinc-900 border border-zinc-850 rounded-lg px-2.5 py-2 text-zinc-350 focus:text-zinc-100 outline-none cursor-pointer flex-1 sm:flex-initial"
                    >
                      <option value="mentions">Mentions</option>
                      <option value="timeline">Timeline</option>
                    </select>

                    <button
                      onClick={() => refetchTweets()}
                      disabled={!twitterUserId || isTweetsLoading}
                      className="flex items-center justify-center gap-1.5 px-3 py-2 bg-zinc-900 border border-zinc-850 rounded-lg text-zinc-300 hover:text-zinc-50 hover:bg-zinc-800 transition-all cursor-pointer disabled:opacity-50"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Tweet List */}
                <div className="space-y-3">
                  {!twitterUserId ? (
                    <div className="py-12 text-center text-zinc-500 italic text-xs">
                      Enter a Twitter numerical User ID to fetch Mentions or Timeline.
                    </div>
                  ) : isTweetsLoading ? (
                    <div className="py-12 flex justify-center text-zinc-500">
                      <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
                    </div>
                  ) : tweetsError ? (
                    <div className="p-4 border border-dashed border-zinc-800 rounded-lg text-center text-xs text-zinc-500 space-y-2">
                      <AlertTriangle className="w-6 h-6 text-zinc-650 mx-auto" />
                      <p className="font-semibold">Twitter/X API Not Configured</p>
                      <p className="text-[10px] max-w-sm mx-auto">
                        Backend returned configuration warning: TWITTER_BEARER_TOKEN is not set. Ensure tokens are initialized in environment variables.
                      </p>
                    </div>
                  ) : tweets && tweets.length > 0 ? (
                    <div className="divide-y divide-zinc-900">
                      {tweets.map((tweet: any) => {
                        const isSelected = selectedTweet?.id === tweet.id;
                        return (
                          <div
                            key={tweet.id}
                            onClick={() => {
                              setSelectedTweet(tweet);
                              setTwitterReplyText('');
                            }}
                            className={`p-4 cursor-pointer hover:bg-zinc-900/20 transition-all flex flex-col gap-2 rounded-lg ${
                              isSelected ? 'bg-zinc-900/40 border border-zinc-800' : ''
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-zinc-400 flex items-center gap-1">
                                <User className="w-3.5 h-3.5 text-zinc-500" />
                                {tweet.author_id || 'X User'}
                              </span>
                              {tweet.created_at && (
                                <span className="text-[10px] font-mono text-zinc-500">
                                  {new Date(tweet.created_at).toLocaleString()}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-zinc-200 font-normal leading-relaxed">
                              {tweet.text}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="py-12 text-center text-zinc-500 italic text-xs">
                      No tweets returned for this ID.
                    </div>
                  )}
                </div>

              </div>
            </div>

            {/* Twitter Reply Drawer/Pane */}
            <div className="space-y-6">
              <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
                <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                  <MessageSquare className="w-4 h-4 text-zinc-400" />
                  <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Reply Composer</h2>
                </div>

                {twitterStatus && (
                  <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/20 p-4 text-xs text-emerald-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                    <span>{twitterStatus}</span>
                  </div>
                )}

                {twitterError && (
                  <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-xs text-red-400">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
                    <span>{twitterError}</span>
                  </div>
                )}

                {selectedTweet ? (
                  <div className="space-y-4">
                    {/* Selected tweet preview */}
                    <div className="p-3 bg-zinc-950 border border-zinc-900 rounded-lg text-xs text-zinc-400 space-y-2">
                      <p className="font-semibold text-zinc-300">Replying to {selectedTweet.author_id || 'X User'}:</p>
                      <p className="italic">"{selectedTweet.text}"</p>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                        AI Suggested Reply
                      </label>
                      <textarea
                        value={twitterReplyText}
                        onChange={(e) => setTwitterReplyText(e.target.value)}
                        placeholder="Drafted reply will appear here..."
                        rows={6}
                        className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-3 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all resize-none"
                      />
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={() => generateTwitterReply(selectedTweet)}
                        disabled={isGeneratingTwitterReply}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-xs font-semibold text-zinc-300 border border-zinc-800 transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isGeneratingTwitterReply ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-zinc-500" />}
                        Generate
                      </button>

                      <button
                        onClick={postTwitterReply}
                        disabled={isPostingTwitterReply || !twitterReplyText}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isPostingTwitterReply ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        Post Reply
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="py-12 text-center text-zinc-500 italic text-xs">
                    Select a tweet from the left feed to draft or publish replies.
                  </div>
                )}

              </div>
            </div>

          </div>
        )}

      </div>
    </SidebarLayout>
  );
}
