'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { 
  CheckCircle2, 
  ExternalLink, 
  Loader2, 
  ArrowRight, 
  Mail, 
  MessageSquare, 
  Send, 
  Share2, 
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';

export default function ApplicationIntegrationsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const activePopup = useRef<Window | null>(null);
  const pollingInterval = useRef<any>(null);

  // Fetch connected services status from backend
  const { data: connectedServices = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['onboarding-connected-services'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/preferences');
      return response.data.connected_services || [];
    },
    refetchInterval: 3000, // Poll during onboarding connect
  });

  useEffect(() => {
    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    };
  }, []);

  const isConnected = (provider: string) => {
    const service = connectedServices.find((s: any) => s.provider === provider);
    return service?.connected === true;
  };

  // Connect Google / Gmail
  const handleConnectGoogle = async () => {
    setConnectingProvider('google');
    try {
      const response = await apiClient.get('/gmail/authorize');
      const { authorization_url } = response.data;

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'Google Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        const check = await apiClient.get('/settings/preferences');
        const status = check.data.connected_services.find((s: any) => s.provider === 'google')?.connected;
        if (status) {
          clearInterval(pollingInterval.current);
          setConnectingProvider(null);
          if (popup) popup.close();
          refetch();
        }
      }, 2000);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize Google authorization.');
      setConnectingProvider(null);
    }
  };

  // Connect Slack
  const handleConnectSlack = async () => {
    setConnectingProvider('slack');
    try {
      const response = await apiClient.get('/slack/login');
      const { authorization_url } = response.data;

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'Slack Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        const check = await apiClient.get('/settings/preferences');
        const status = check.data.connected_services.find((s: any) => s.provider === 'slack')?.connected;
        if (status) {
          clearInterval(pollingInterval.current);
          setConnectingProvider(null);
          if (popup) popup.close();
          refetch();
        }
      }, 2000);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize Slack authorization.');
      setConnectingProvider(null);
    }
  };

  // Connect Twitter / X
  const handleConnectTwitter = async () => {
    setConnectingProvider('twitter');
    try {
      const response = await apiClient.get('/twitter/authorize');
      const { authorization_url } = response.data;

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'Twitter Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        const check = await apiClient.get('/settings/preferences');
        const status = check.data.connected_services.find((s: any) => s.provider === 'twitter')?.connected;
        if (status) {
          clearInterval(pollingInterval.current);
          setConnectingProvider(null);
          if (popup) popup.close();
          refetch();
        }
      }, 2000);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize Twitter authorization.');
      setConnectingProvider(null);
    }
  };

  // Disconnect handler
  const handleDisconnect = async (provider: string) => {
    try {
      await apiClient.post(`/settings/disconnect/${provider}`);
      refetch();
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to disconnect ${provider}`);
    }
  };

  const handleNextOrSkip = () => {
    router.push('/onboarding/run');
  };

  const hasAnyConnected = connectedServices.some((s: any) => s.connected);

  return (
    <div className="flex min-h-screen flex-col justify-between bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Tech grid background */}
      <div className="tech-grid opacity-30"></div>

      {/* Floating Ambient Blobs */}
      <div className="glowing-blob-container">
        <div className="glowing-blob blob-purple animate-blob-1 -top-20 -left-20"></div>
        <div className="glowing-blob blob-blue animate-blob-2 -bottom-40 -right-20"></div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center relative z-10 my-auto">
        <div className="w-full max-w-3xl space-y-8">
          
          {/* Header */}
          <div className="flex flex-col items-center justify-center text-center">
            <Logo size={44} className="mb-2" />
            <h2 className="mt-4 text-2xl md:text-3xl font-bold tracking-tight text-zinc-50">
              Connect your applications
            </h2>
            <p className="mt-2 text-sm text-zinc-400 max-w-md">
              Connect the services you want SidekickAI to monitor. You can connect services now or manage them later in Settings.
            </p>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* Google / Gmail */}
            <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-900 backdrop-blur-md flex flex-col justify-between space-y-4 hover:border-zinc-800 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                    <Mail className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-100">Google / Gmail</h3>
                    <p className="text-xs text-zinc-500">Inbox, Emails & Calendar</p>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isConnected('google')
                    ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/50'
                    : 'bg-zinc-950 text-zinc-500 border-zinc-900'
                }`}>
                  {isConnected('google') ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              
              <div>
                {isConnected('google') ? (
                  <button
                    onClick={() => handleDisconnect('google')}
                    className="w-full py-2 bg-zinc-950 hover:bg-rose-950/20 text-zinc-400 hover:text-rose-400 rounded-lg text-xs font-medium border border-zinc-900 hover:border-rose-900/30 transition-all cursor-pointer"
                  >
                    Disconnect Service
                  </button>
                ) : (
                  <button
                    onClick={handleConnectGoogle}
                    disabled={connectingProvider === 'google'}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-zinc-900 hover:bg-zinc-850 disabled:opacity-50 text-zinc-100 rounded-lg text-xs font-semibold border border-zinc-800 transition-all cursor-pointer"
                  >
                    {connectingProvider === 'google' ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Connecting popup...
                      </>
                    ) : (
                      <>
                        Authorize Google
                        <ExternalLink className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Slack */}
            <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-900 backdrop-blur-md flex flex-col justify-between space-y-4 hover:border-zinc-800 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-100">Slack Integration</h3>
                    <p className="text-xs text-zinc-500">DMs, Channel mentions & alerts</p>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isConnected('slack')
                    ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/50'
                    : 'bg-zinc-950 text-zinc-500 border-zinc-900'
                }`}>
                  {isConnected('slack') ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              
              <div>
                {isConnected('slack') ? (
                  <button
                    onClick={() => handleDisconnect('slack')}
                    className="w-full py-2 bg-zinc-950 hover:bg-rose-950/20 text-zinc-400 hover:text-rose-400 rounded-lg text-xs font-medium border border-zinc-900 hover:border-rose-900/30 transition-all cursor-pointer"
                  >
                    Disconnect Service
                  </button>
                ) : (
                  <button
                    onClick={handleConnectSlack}
                    disabled={connectingProvider === 'slack'}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-zinc-900 hover:bg-zinc-850 disabled:opacity-50 text-zinc-100 rounded-lg text-xs font-semibold border border-zinc-800 transition-all cursor-pointer"
                  >
                    {connectingProvider === 'slack' ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Connecting popup...
                      </>
                    ) : (
                      <>
                        Authorize Slack
                        <ExternalLink className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Telegram */}
            <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-900 backdrop-blur-md flex flex-col justify-between space-y-4 hover:border-zinc-800 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
                    <Send className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-100">Telegram Client</h3>
                    <p className="text-xs text-zinc-500">Direct messages & chat logs</p>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isConnected('telegram')
                    ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/50'
                    : 'bg-zinc-950 text-zinc-500 border-zinc-900'
                }`}>
                  {isConnected('telegram') ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              
              <div>
                {isConnected('telegram') ? (
                  <button
                    onClick={() => handleDisconnect('telegram')}
                    className="w-full py-2 bg-zinc-950 hover:bg-rose-950/20 text-zinc-400 hover:text-rose-400 rounded-lg text-xs font-medium border border-zinc-900 hover:border-rose-900/30 transition-all cursor-pointer"
                  >
                    Disconnect Service
                  </button>
                ) : (
                  <button
                    onClick={() => router.push('/settings')}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-zinc-900 hover:bg-zinc-850 text-zinc-300 rounded-lg text-xs font-medium border border-zinc-800 transition-all cursor-pointer"
                  >
                    Configure in Settings
                  </button>
                )}
              </div>
            </div>

            {/* Twitter / X */}
            <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-900 backdrop-blur-md flex flex-col justify-between space-y-4 hover:border-zinc-800 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
                    <Share2 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-100">Twitter / X Desk</h3>
                    <p className="text-xs text-zinc-500">Mentions & reply posting</p>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isConnected('twitter')
                    ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/50'
                    : 'bg-zinc-950 text-zinc-500 border-zinc-900'
                }`}>
                  {isConnected('twitter') ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              
              <div>
                {isConnected('twitter') ? (
                  <button
                    onClick={() => handleDisconnect('twitter')}
                    className="w-full py-2 bg-zinc-950 hover:bg-rose-950/20 text-zinc-400 hover:text-rose-400 rounded-lg text-xs font-medium border border-zinc-900 hover:border-rose-900/30 transition-all cursor-pointer"
                  >
                    Disconnect Service
                  </button>
                ) : (
                  <button
                    onClick={handleConnectTwitter}
                    disabled={connectingProvider === 'twitter'}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-zinc-900 hover:bg-zinc-850 disabled:opacity-50 text-zinc-100 rounded-lg text-xs font-semibold border border-zinc-800 transition-all cursor-pointer"
                  >
                    {connectingProvider === 'twitter' ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Connecting popup...
                      </>
                    ) : (
                      <>
                        Authorize Twitter
                        <ExternalLink className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

          </div>

          {/* Action Bar */}
          <div className="flex items-center justify-between pt-6 border-t border-zinc-900">
            <button
              onClick={handleNextOrSkip}
              className="px-4 py-2.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-all cursor-pointer"
            >
              Skip for now
            </button>

            <button
              onClick={handleNextOrSkip}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
            >
              {hasAnyConnected ? 'Continue to Run AI' : 'Next'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

        </div>
      </div>

      <footer className="w-full text-center text-xs text-zinc-650 border-t border-zinc-900/40 pt-6 mt-8 relative z-10">
        <p>&copy; {new Date().getFullYear()} SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
