'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as zod from 'zod';
import Cookies from 'js-cookie';
import { 
  Settings, 
  User, 
  Lock, 
  AlertTriangle, 
  CheckCircle2, 
  HelpCircle,
  ExternalLink,
  Loader2,
  Power,
  ShieldAlert,
  Disc,
  Trash2
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

// Validation Schemas
const profileSchema = zod.object({
  fullName: zod.string().min(1, { message: 'Full name is required' }),
});

const passwordSchema = zod.object({
  currentPassword: zod.string().min(1, { message: 'Current password is required' }),
  newPassword: zod.string().min(8, { message: 'New password must be at least 8 characters' }),
  confirmPassword: zod.string().min(8, { message: 'Confirm password must be at least 8 characters' }),
}).refine(data => data.newPassword === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword']
});

type ProfileSchema = zod.infer<typeof profileSchema>;
type PasswordSchema = zod.infer<typeof passwordSchema>;

export default function SettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Google OAuth popup polling reference
  const [isGoogleConnecting, setIsGoogleConnecting] = useState(false);
  const [isWhatsAppConnecting, setIsWhatsAppConnecting] = useState(false);
  const [isLinkedInConnecting, setIsLinkedInConnecting] = useState(false);
  const pollingInterval = useRef<any>(null);
  const activePopup = useRef<any>(null);

  // Fetch current user profile
  const { data: user, isLoading: isUserLoading } = useQuery({
    queryKey: ['user-settings'],
    queryFn: async () => {
      const response = await apiClient.get('/auth/me');
      return response.data;
    },
  });

  // Fetch integrations/preferences
  const { data: preferences, isLoading: isPrefLoading } = useQuery({
    queryKey: ['preferences-settings'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/preferences');
      return response.data;
    },
  });

  const connectedServices = preferences?.connected_services || [];
  const googlePref = connectedServices.find((s: any) => s.provider === 'google');
  const twitterPref = connectedServices.find((s: any) => s.provider === 'twitter');
  const whatsappPref = connectedServices.find((s: any) => s.provider === 'whatsapp');
  const linkedinPref = connectedServices.find((s: any) => s.provider === 'linkedin');
  const telegramPref = connectedServices.find((s: any) => s.provider === 'telegram');
  const discordPref = connectedServices.find((s: any) => s.provider === 'discord');


  const [telegramApiId, setTelegramApiId] = useState('');
  const [telegramApiHash, setTelegramApiHash] = useState('');
  const [telegramPhoneNumber, setTelegramPhoneNumber] = useState('');
  const [telegramSessionString, setTelegramSessionString] = useState('');
  const [telegramOtpCode, setTelegramOtpCode] = useState('');
  const [telegramPassword, setTelegramPassword] = useState('');
  const [telegramPhoneCodeHash, setTelegramPhoneCodeHash] = useState('');
  const [telegramAuthState, setTelegramAuthState] = useState<'idle' | 'code_sent' | 'requires_password'>('idle');
  const [telegramOtpLoading, setTelegramOtpLoading] = useState(false);
  const [telegramOtpError, setTelegramOtpError] = useState<string | null>(null);
  const [isDiscordConnecting, setIsDiscordConnecting] = useState(false);
  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    setValue: setProfileValue,
    formState: { errors: profileErrors, isSubmitting: isProfileSubmitting },
  } = useForm<ProfileSchema>({
    resolver: zodResolver(profileSchema),
  });

  const {
    register: registerPassword,
    handleSubmit: handleSubmitPassword,
    reset: resetPasswordForm,
    formState: { errors: passwordErrors, isSubmitting: isPasswordSubmitting },
  } = useForm<PasswordSchema>({
    resolver: zodResolver(passwordSchema),
  });

  // Set default full name when user details load
  useEffect(() => {
    if (user?.full_name) {
      setProfileValue('fullName', user.full_name);
    }
  }, [user, setProfileValue]);

  // Clean up polling interval and register message handler
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Validate target origin for security
      if (event.origin !== window.location.origin) return;

      if (event.data === 'gmail-connected') {
        setIsGoogleConnecting(false);
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        if (activePopup.current) {
          activePopup.current.close();
          activePopup.current = null;
        }
        queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
        queryClient.invalidateQueries({ queryKey: ['preferences'] });
      } else if (event.data === 'whatsapp-connected') {
        setIsWhatsAppConnecting(false);
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        if (activePopup.current) {
          activePopup.current.close();
          activePopup.current = null;
        }
        queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
        queryClient.invalidateQueries({ queryKey: ['preferences'] });
      } else if (event.data && event.data.type === 'whatsapp-connection-error') {
        setIsWhatsAppConnecting(false);
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        alert(`WhatsApp Business Account connection failed:\n\n${event.data.message}\n\nPlease ensure you have a WhatsApp Business Account (WABA) with a registered business phone number.`);
      } else if (event.data === 'linkedin-connected') {
        setIsLinkedInConnecting(false);
        if (pollingInterval.current) clearInterval(pollingInterval.current);
        if (activePopup.current) {
          activePopup.current.close();
          activePopup.current = null;
        }
        queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
        queryClient.invalidateQueries({ queryKey: ['preferences'] });
      }
    };
    window.addEventListener('message', handleMessage);

    return () => {
      window.removeEventListener('message', handleMessage);
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    };
  }, [queryClient]);

  // Profile update mutation
  const updateProfileMutation = useMutation({
    mutationFn: async (data: ProfileSchema) => {
      setProfileSuccess(null);
      setProfileError(null);
      const response = await apiClient.put('/auth/me', {
        full_name: data.fullName,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setProfileSuccess('Profile updated successfully.');
      queryClient.setQueryData(['user'], data);
      queryClient.setQueryData(['user-settings'], data);
    },
    onError: (err: any) => {
      setProfileError(err.response?.data?.detail || 'Failed to update profile.');
    }
  });

  // Password update mutation
  const updatePasswordMutation = useMutation({
    mutationFn: async (data: PasswordSchema) => {
      setPasswordSuccess(null);
      setPasswordError(null);
      const response = await apiClient.put('/auth/me', {
        current_password: data.currentPassword,
        new_password: data.newPassword,
      });
      return response.data;
    },
    onSuccess: () => {
      setPasswordSuccess('Password changed successfully.');
      resetPasswordForm();
    },
    onError: (err: any) => {
      setPasswordError(err.response?.data?.detail || 'Failed to update password.');
    }
  });
  // Disconnect service mutation
  const disconnectMutation = useMutation({
    mutationFn: async (provider: string) => {
      if (provider === 'google') {
        const response = await apiClient.delete('/gmail/disconnect');
        return response.data;
      } else if (provider === 'linkedin') {
        const response = await apiClient.delete('/linkedin/disconnect');
        return response.data;
      } else if (provider === 'telegram') {
        const response = await apiClient.delete('/telegram/disconnect');
        return response.data;
      } else {
        const response = await apiClient.post(`/settings/disconnect/${provider}`);
        return response.data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
      queryClient.invalidateQueries({ queryKey: ['preferences'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to disconnect service.');
    }
  });

  // Clear application data mutation
  const clearDataMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/settings/clear-data');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      alert('Application data cleared successfully! Your dashboard is now clean.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to clear application data.');
    }
  });



  // Connect Telegram mutation (direct phone setup or session string setup)
  const connectTelegramMutation = useMutation({
    mutationFn: async (data: { phone_number: string; session_string?: string }) => {
      const response = await apiClient.post('/telegram/connect', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
      queryClient.invalidateQueries({ queryKey: ['preferences'] });
      alert('Telegram integrated successfully!');
      setTelegramPhoneNumber('');
      setTelegramSessionString('');
      setTelegramAuthState('idle');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to connect Telegram.');
    }
  });

  // Request Telegram login OTP
  const sendTelegramCodeMutation = useMutation({
    mutationFn: async (data: { phone_number: string }) => {
      setTelegramOtpLoading(true);
      setTelegramOtpError(null);
      const response = await apiClient.post('/telegram/send-code', data);
      return response.data;
    },
    onSuccess: (data) => {
      setTelegramPhoneCodeHash(data.phone_code_hash);
      setTelegramAuthState('code_sent');
      alert('Verification OTP code requested! Please check your Telegram app.');
    },
    onError: (err: any) => {
      setTelegramOtpError(err.response?.data?.detail || 'Failed to send verification code.');
    },
    onSettled: () => {
      setTelegramOtpLoading(false);
    }
  });



  // Verify Telegram OTP code mutation
  const verifyTelegramCodeMutation = useMutation({
    mutationFn: async (data: { phone_number: string; code: string; phone_code_hash: string }) => {
      setTelegramOtpLoading(true);
      setTelegramOtpError(null);
      const response = await apiClient.post('/telegram/verify-code', data);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'requires_password') {
        setTelegramAuthState('requires_password');
        setTelegramPhoneCodeHash(data.phone_code_hash);
        alert('Two-Step Verification (2FA) is enabled on your Telegram account. Please enter your account password.');
      } else {
        queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
        queryClient.invalidateQueries({ queryKey: ['preferences'] });
        alert('Telegram User API client authenticated successfully!');
        setTelegramPhoneNumber('');
        setTelegramOtpCode('');
        setTelegramPhoneCodeHash('');
        setTelegramAuthState('idle');
      }
    },
    onError: (err: any) => {
      setTelegramOtpError(err.response?.data?.detail || 'OTP verification failed.');
    },
    onSettled: () => {
      setTelegramOtpLoading(false);
    }
  });

  // Verify Telegram 2FA Password mutation
  const verifyTelegramPasswordMutation = useMutation({
    mutationFn: async (data: { phone_number: string; password: string }) => {
      setTelegramOtpLoading(true);
      setTelegramOtpError(null);
      const response = await apiClient.post('/telegram/verify-password', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
      queryClient.invalidateQueries({ queryKey: ['preferences'] });
      alert('Telegram 2FA authenticated successfully!');
      setTelegramPhoneNumber('');
      setTelegramPassword('');
      setTelegramOtpCode('');
      setTelegramPhoneCodeHash('');
      setTelegramAuthState('idle');
    },
    onError: (err: any) => {
      setTelegramOtpError(err.response?.data?.detail || 'Invalid Two-step password.');
    },
    onSettled: () => {
      setTelegramOtpLoading(false);
    }
  });


  // Google OAuth flow initiator
  const handleConnectGoogle = async () => {
    setIsGoogleConnecting(true);
    try {
      const response = await apiClient.get('/gmail/authorize');
      const { authorization_url } = response.data;
      
      // Store current token in cookies for redirect callback authentication
      const token = Cookies.get('access_token');
      if (token) {
        // Set cookie explicitly on domain
        Cookies.set('access_token', token, { expires: 1, sameSite: 'lax' });
      }

      // Open Google Consent Screen in popup
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

      // Poll connection status
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        try {
          const prefCheck = await apiClient.get('/settings/preferences');
          const googleStatus = prefCheck.data.connected_services.find((s: any) => s.provider === 'google')?.connected;
          
          if (googleStatus) {
            clearInterval(pollingInterval.current);
            setIsGoogleConnecting(false);
            if (popup) popup.close();
            queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
            queryClient.invalidateQueries({ queryKey: ['preferences'] });
          }
        } catch (e) {
          console.error(e);
        }
      }, 2500);

    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize Google authorization.');
      setIsGoogleConnecting(false);
    }
  };

  const handleConnectWhatsApp = async () => {
    setIsWhatsAppConnecting(true);
    try {
      const response = await apiClient.get('/whatsapp/authorize');
      const { authorization_url } = response.data;
      
      const token = Cookies.get('access_token');
      if (token) {
        Cookies.set('access_token', token, { expires: 1, sameSite: 'lax' });
      }

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'WhatsApp Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        try {
          const prefCheck = await apiClient.get('/settings/preferences');
          const whatsappStatus = prefCheck.data.connected_services.find((s: any) => s.provider === 'whatsapp')?.connected;
          
          if (whatsappStatus) {
            clearInterval(pollingInterval.current);
            setIsWhatsAppConnecting(false);
            if (popup) popup.close();
            queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
            queryClient.invalidateQueries({ queryKey: ['preferences'] });
          }
        } catch (e) {
          console.error(e);
        }
      }, 2500);

    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize WhatsApp authorization.');
      setIsWhatsAppConnecting(false);
    }
  };

  const handleConnectLinkedIn = async () => {
    setIsLinkedInConnecting(true);
    try {
      const response = await apiClient.get('/linkedin/login');
      const { authorization_url } = response.data;
      
      const token = Cookies.get('access_token');
      if (token) {
        Cookies.set('access_token', token, { expires: 1, sameSite: 'lax' });
      }

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'LinkedIn Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        try {
          const prefCheck = await apiClient.get('/settings/preferences');
          const linkedinStatus = prefCheck.data.connected_services.find((s: any) => s.provider === 'linkedin')?.connected;
          
          if (linkedinStatus) {
            clearInterval(pollingInterval.current);
            setIsLinkedInConnecting(false);
            if (popup) popup.close();
            queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
            queryClient.invalidateQueries({ queryKey: ['preferences'] });
          }
        } catch (e) {
          console.error(e);
        }
      }, 2500);

    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize LinkedIn authorization.');
      setIsLinkedInConnecting(false);
    }
  };

  const handleConnectDiscord = async () => {
    setIsDiscordConnecting(true);
    try {
      const response = await apiClient.get(`/discord/login?t=${Date.now()}`);
      const { authorization_url } = response.data;
      
      const token = Cookies.get('access_token');
      if (token) {
        Cookies.set('access_token', token, { expires: 1, sameSite: 'lax' });
      }

      const width = 500;
      const height = 650;
      const left = window.screenX + (window.innerWidth - width) / 2;
      const top = window.screenY + (window.innerHeight - height) / 2;
      const popup = window.open(
        authorization_url,
        'Discord Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      activePopup.current = popup;

      if (pollingInterval.current) clearInterval(pollingInterval.current);
      pollingInterval.current = setInterval(async () => {
        try {
          const prefCheck = await apiClient.get('/settings/preferences');
          const discordStatus = prefCheck.data.connected_services.find((s: any) => s.provider === 'discord')?.connected;
          
          if (discordStatus) {
            clearInterval(pollingInterval.current);
            setIsDiscordConnecting(false);
            if (popup) popup.close();
            queryClient.invalidateQueries({ queryKey: ['preferences-settings'] });
            queryClient.invalidateQueries({ queryKey: ['preferences'] });
          }
        } catch (e) {
          console.error(e);
        }
      }, 2500);

    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to initialize Discord authorization.');
      setIsDiscordConnecting(false);
    }
  };

  const handleDeactivateAccount = async () => {
    if (!confirm('Are you absolutely sure you want to deactivate your assistant profile? This action is irreversible.')) {
      return;
    }
    setIsDeleting(true);
    try {
      await apiClient.delete('/auth/me');
      Cookies.remove('access_token');
      router.push('/login');
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to deactivate account.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-5xl mx-auto h-full overflow-y-auto">
        
        {/* Header */}
        <div className="border-b border-zinc-900 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Settings & Integrations</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Configure integrations, credentials, and manage your security profile.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left: General Settings Forms */}
          <div className="lg:col-span-2 space-y-8">
            
            {/* Profile Update */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <User className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Profile Information</h2>
              </div>

              {profileSuccess && (
                <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/20 p-4 text-xs text-emerald-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                  <span>{profileSuccess}</span>
                </div>
              )}

              {profileError && (
                <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-xs text-red-400">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
                  <span>{profileError}</span>
                </div>
              )}

              <form onSubmit={handleSubmitProfile((data) => updateProfileMutation.mutate(data))} className="space-y-4">
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Account Email Address
                  </label>
                  <input
                    type="text"
                    disabled
                    value={user?.email || ''}
                    className="w-full bg-zinc-950/40 border border-zinc-900 rounded-lg px-3 py-2 text-xs text-zinc-550 outline-none cursor-not-allowed"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Full Name
                  </label>
                  <input
                    type="text"
                    {...registerProfile('fullName')}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                  />
                  {profileErrors.fullName && (
                    <p className="text-xs text-red-400 mt-1">{profileErrors.fullName.message}</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isProfileSubmitting}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                >
                  {isProfileSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Changes
                </button>
              </form>
            </div>

            {/* Password Change */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Lock className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Change Security Credentials</h2>
              </div>

              {passwordSuccess && (
                <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/20 p-4 text-xs text-emerald-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                  <span>{passwordSuccess}</span>
                </div>
              )}

              {passwordError && (
                <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-xs text-red-400">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
                  <span>{passwordError}</span>
                </div>
              )}

              <form onSubmit={handleSubmitPassword((data) => updatePasswordMutation.mutate(data))} className="space-y-4">
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Current Password
                  </label>
                  <input
                    type="password"
                    {...registerPassword('currentPassword')}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                  />
                  {passwordErrors.currentPassword && (
                    <p className="text-xs text-red-400 mt-1">{passwordErrors.currentPassword.message}</p>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      New Password
                    </label>
                    <input
                      type="password"
                      {...registerPassword('newPassword')}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                    />
                    {passwordErrors.newPassword && (
                      <p className="text-xs text-red-400 mt-1">{passwordErrors.newPassword.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      {...registerPassword('confirmPassword')}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                    />
                    {passwordErrors.confirmPassword && (
                      <p className="text-xs text-red-400 mt-1">{passwordErrors.confirmPassword.message}</p>
                    )}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isPasswordSubmitting}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                >
                  {isPasswordSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Change Password
                </button>
              </form>
            </div>

            {/* Clear/Reset Application Data */}
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-4">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Trash2 className="w-4 h-4 text-amber-500" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Reset Application Data</h2>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Clearing application data resets your inbox state by deleting all synced messages, direct chats, and AI briefings. This allows you to start with a clean slate. Discovered integrations and user settings will not be affected.
              </p>
              <button
                onClick={() => {
                  if (confirm('Are you sure you want to clear all synced messages and memory logs? This action is irreversible.')) {
                    clearDataMutation.mutate();
                  }
                }}
                disabled={clearDataMutation.isPending}
                className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-zinc-950 hover:bg-amber-950/20 hover:text-amber-400 border border-zinc-850 hover:border-amber-900/20 text-xs font-semibold text-zinc-400 transition-all cursor-pointer disabled:opacity-50"
              >
                {clearDataMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Clearing data...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    Clear All Test Messages & Logs
                  </>
                )}
              </button>
            </div>

            {/* Danger Zone */}
            <div className="bg-zinc-950 border border-red-950/60 rounded-xl p-6 space-y-4">
              <div className="flex items-center gap-2 border-b border-red-950/20 pb-3">
                <ShieldAlert className="w-4 h-4 text-red-400" />
                <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider">Danger Zone</h2>
              </div>
              <p className="text-xs text-zinc-450 leading-relaxed font-normal">
                Deactivating your profile will disable all background messaging cycles, terminate Gmail synchronization, and log you out. Account deactivation can be undone by logging back in with your username.
              </p>
              <button
                onClick={handleDeactivateAccount}
                disabled={isDeleting}
                className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-red-950/20 hover:bg-red-950/40 border border-red-900/30 text-xs font-semibold text-red-400 transition-all cursor-pointer"
              >
                {isDeleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Deactivate Profile Account
              </button>
            </div>

          </div>

          {/* Right: Connected Integrations Panel */}
          <div className="space-y-6">
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Power className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Connected Services</h2>
              </div>

              {isPrefLoading ? (
                <div className="py-8 flex justify-center text-zinc-500">
                  <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Google Card */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-255">Google Integration</h3>
                        <p className="text-[10px] text-zinc-500">Gmail, Calendar sync</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        googlePref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {googlePref?.connected ? 'Active' : 'Disconnected'}
                      </span>
                    </div>
                    {googlePref?.connected ? (
                      <div className="space-y-2">
                        {googlePref.connected_at && (
                          <p className="text-[9px] font-mono text-zinc-500">Linked: {new Date(googlePref.connected_at).toLocaleString()}</p>
                        )}
                        <button
                          onClick={() => disconnectMutation.mutate('google')}
                          className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                        >
                          Revoke Access
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleConnectGoogle}
                        disabled={isGoogleConnecting}
                        className="flex items-center justify-center gap-1.5 w-full py-2 bg-zinc-100 hover:bg-zinc-200 rounded text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isGoogleConnecting ? (
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

                  {/* Twitter Card */}
                  <div className="space-y-3 pt-4 border-t border-zinc-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-255">Twitter / X Desk</h3>
                        <p className="text-[10px] text-zinc-500">Mentions, Reply posting</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        twitterPref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {twitterPref?.connected ? 'Active' : 'Offline'}
                      </span>
                    </div>
                    {twitterPref?.connected ? (
                      <button
                        onClick={() => disconnectMutation.mutate('twitter')}
                        className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                      >
                        Disconnect Service
                      </button>
                    ) : (
                      <div className="p-3 bg-zinc-950/60 border border-zinc-900 rounded text-[10px] text-zinc-500 leading-relaxed">
                        Read-only mentions are pulled automatically from your global system environment variables when set.
                      </div>
                    )}
                  </div>

                  {/* WhatsApp Card */}
                  <div className="space-y-3 pt-4 border-t border-zinc-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-200">WhatsApp Business Account</h3>
                        <p className="text-[10px] text-zinc-500">Business contacts, Customer messages</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        whatsappPref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {whatsappPref?.connected ? 'Active' : 'Offline'}
                      </span>
                    </div>
                    {whatsappPref?.connected ? (
                      <button
                        onClick={() => disconnectMutation.mutate('whatsapp')}
                        className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                      >
                        Disconnect Service
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={handleConnectWhatsApp}
                          disabled={isWhatsAppConnecting}
                          className="w-full flex items-center justify-center gap-1.5 py-2 bg-zinc-900 hover:bg-zinc-800 rounded text-xs font-semibold text-zinc-50 border border-zinc-850 hover:border-zinc-700 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isWhatsAppConnecting ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Connecting popup...
                            </>
                          ) : (
                            <>
                              Connect your WhatsApp Business Account
                              <ExternalLink className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                        <div className="text-[10px] text-zinc-450 bg-zinc-900/40 border border-zinc-900/80 rounded-lg p-2.5 mt-2 leading-relaxed">
                          <span className="text-amber-500 font-semibold block mb-0.5">Platform Requirement:</span>
                          Requires an existing WhatsApp Business Account (WABA) with a registered business phone number. Personal WhatsApp numbers are not supported.
                        </div>
                      </>
                    )}
                  </div>

                  {/* LinkedIn Card */}
                  <div className="space-y-3 pt-4 border-t border-zinc-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-200">LinkedIn Integration</h3>
                        <p className="text-[10px] text-zinc-500">Profile sync & auto-posting</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        linkedinPref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {linkedinPref?.connected ? 'Active' : 'Offline'}
                      </span>
                    </div>
                    {linkedinPref?.connected ? (
                      <button
                        onClick={() => disconnectMutation.mutate('linkedin')}
                        className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                      >
                        Disconnect Service
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={handleConnectLinkedIn}
                          disabled={isLinkedInConnecting}
                          className="w-full flex items-center justify-center gap-1.5 py-2 bg-zinc-900 hover:bg-zinc-800 rounded text-xs font-semibold text-zinc-50 border border-zinc-850 hover:border-zinc-700 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isLinkedInConnecting ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Connecting popup...
                            </>
                          ) : (
                            <>
                              Authorize LinkedIn
                              <ExternalLink className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                        <div className="text-[10px] text-zinc-450 bg-zinc-900/40 border border-zinc-900/80 rounded-lg p-2.5 mt-2 leading-relaxed">
                          <span className="text-indigo-400 font-semibold block mb-0.5">Integration Access:</span>
                          Allows profile sync and sharing auto-posts. Read access to personal DMs/inbox is not supported by the LinkedIn API.
                        </div>
                      </>
                    )}
                  </div>

                  {/* Telegram Card */}
                  <div className="space-y-4 pt-4 border-t border-zinc-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-200">Telegram User Client Integration</h3>
                        <p className="text-[10px] text-zinc-500">Sync dialogs and chats from your personal account using MTProto Client API</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        telegramPref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {telegramPref?.connected ? 'Active' : 'Offline'}
                      </span>
                    </div>

                    {telegramPref?.connected ? (
                      <div className="space-y-3">
                        <div className="bg-zinc-950/60 border border-zinc-900/80 rounded-xl p-3.5 space-y-2 text-xs">
                          <div className="flex justify-between">
                            <span className="text-zinc-500">Phone Number:</span>
                            <span className="text-zinc-300 font-mono">{telegramPref?.phone_number || 'Configured'}</span>
                          </div>
                          {user?.is_admin && (
                            <div className="flex justify-between">
                              <span className="text-zinc-500">Session String:</span>
                              <span className="text-zinc-300 font-mono">{telegramPref?.session_string || 'Configured'}</span>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => disconnectMutation.mutate('telegram')}
                          className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                        >
                          Disconnect Account
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="space-y-2">
                          <label className="block text-[10px] uppercase tracking-wider font-semibold text-zinc-400">
                            Phone Number
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. +1234567890"
                            value={telegramPhoneNumber}
                            onChange={(e) => setTelegramPhoneNumber(e.target.value)}
                            disabled={telegramAuthState !== 'idle'}
                            className="w-full bg-zinc-955 border border-zinc-850 rounded px-2.5 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                          />
                        </div>

                        {telegramOtpError && (
                          <div className="text-[10px] text-red-400 bg-red-950/20 border border-red-900/20 rounded p-2">
                            {telegramOtpError}
                          </div>
                        )}

                        {telegramAuthState === 'idle' && (
                          <div className="space-y-3">
                            <button
                              onClick={() => {
                                if (!telegramPhoneNumber) {
                                  alert('Please enter your Telegram Phone Number.');
                                  return;
                                }
                                sendTelegramCodeMutation.mutate({
                                  phone_number: telegramPhoneNumber
                                });
                              }}
                              disabled={telegramOtpLoading}
                              className="w-full flex items-center justify-center gap-1.5 py-2 bg-zinc-900 hover:bg-zinc-855 rounded text-xs font-semibold text-zinc-50 border border-zinc-850 hover:border-zinc-700 transition-all cursor-pointer disabled:opacity-50"
                            >
                              {telegramOtpLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                              Request OTP Login Code
                            </button>

                            {user?.is_admin && (
                              <>
                                <div className="relative flex py-1 items-center">
                                  <div className="flex-grow border-t border-zinc-900"></div>
                                  <span className="flex-shrink mx-3 text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">Dev Session Direct Connect</span>
                                  <div className="flex-grow border-t border-zinc-900"></div>
                                </div>

                                <div className="space-y-2">
                                  <textarea
                                    placeholder="Paste String Session (StringSession) - DEV MODE ONLY"
                                    value={telegramSessionString}
                                    onChange={(e) => setTelegramSessionString(e.target.value)}
                                    rows={2}
                                    className="w-full bg-zinc-955 border border-zinc-855 rounded p-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all resize-none"
                                  />
                                  <button
                                    onClick={() => {
                                      if (!telegramPhoneNumber || !telegramSessionString) {
                                        alert('Please supply both Phone Number and Session String.');
                                        return;
                                      }
                                      connectTelegramMutation.mutate({
                                        phone_number: telegramPhoneNumber,
                                        session_string: telegramSessionString
                                      });
                                    }}
                                    disabled={connectTelegramMutation.isPending}
                                    className="w-full py-2 bg-zinc-900 hover:bg-zinc-855 border border-zinc-850 text-zinc-300 rounded text-xs font-semibold hover:text-zinc-50 transition-all cursor-pointer disabled:opacity-50"
                                  >
                                    {connectTelegramMutation.isPending ? 'Connecting...' : 'Connect with Session String'}
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        )}

                        {telegramAuthState === 'code_sent' && (
                          <div className="space-y-2.5">
                            <div className="text-[10px] text-amber-400 bg-amber-955/20 border border-amber-900/30 rounded p-2">
                              OTP code has been sent to your Telegram app. Enter it below to sign in.
                            </div>
                            <input
                              type="text"
                              placeholder="Enter Telegram OTP Code"
                              value={telegramOtpCode}
                              onChange={(e) => setTelegramOtpCode(e.target.value)}
                              className="w-full bg-zinc-955 border border-zinc-855 rounded px-2.5 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all text-center tracking-widest font-bold"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() => {
                                  if (!telegramOtpCode) {
                                    alert('Please enter the verification code.');
                                    return;
                                  }
                                  verifyTelegramCodeMutation.mutate({
                                    phone_number: telegramPhoneNumber,
                                    code: telegramOtpCode,
                                    phone_code_hash: telegramPhoneCodeHash
                                  });
                                }}
                                disabled={telegramOtpLoading}
                                className="flex-1 py-2 bg-zinc-100 hover:bg-zinc-200 text-zinc-955 rounded text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                              >
                                {telegramOtpLoading ? 'Verifying...' : 'Verify OTP Code'}
                              </button>
                              <button
                                onClick={() => setTelegramAuthState('idle')}
                                className="px-3 py-2 bg-zinc-955 hover:bg-zinc-900 text-zinc-400 border border-zinc-850 rounded text-xs transition-all cursor-pointer"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}

                        {telegramAuthState === 'requires_password' && (
                          <div className="space-y-2.5">
                            <div className="text-[10px] text-amber-400 bg-amber-955/20 border border-amber-900/30 rounded p-2">
                              Two-Step Verification Password Required. Enter your Telegram cloud password:
                            </div>
                            <input
                              type="password"
                              placeholder="Enter your 2FA Password"
                              value={telegramPassword}
                              onChange={(e) => setTelegramPassword(e.target.value)}
                              className="w-full bg-zinc-955 border border-zinc-850 rounded px-2.5 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all text-center"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() => {
                                  if (!telegramPassword) {
                                    alert('Please enter your 2FA password.');
                                    return;
                                  }
                                  verifyTelegramPasswordMutation.mutate({
                                    phone_number: telegramPhoneNumber,
                                    password: telegramPassword
                                  });
                                }}
                                disabled={telegramOtpLoading}
                                className="flex-1 py-2 bg-zinc-100 hover:bg-zinc-200 text-zinc-955 rounded text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                              >
                                {telegramOtpLoading ? 'Verifying...' : 'Submit Password'}
                              </button>
                              <button
                                onClick={() => {
                                  setTelegramAuthState('idle');
                                  setTelegramPassword('');
                                }}
                                className="px-3 py-2 bg-zinc-955 hover:bg-zinc-900 text-zinc-400 border border-zinc-850 rounded text-xs transition-all cursor-pointer"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}

                        <div className="text-[9px] text-zinc-500 bg-zinc-900/20 border border-zinc-900/80 rounded-lg p-2.5 leading-relaxed">
                          <span className="text-zinc-300 font-semibold block mb-0.5">Easy MTProto Setup:</span>
                          Using pre-configured developer keys. Simply verify your phone number to authorize your personal Telegram client.
                        </div>
                      </div>
                    )}
                  </div>
                  {/* Discord Card */}
                  <div className="space-y-3 pt-4 border-t border-zinc-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-zinc-200">Discord Integration</h3>
                        <p className="text-[10px] text-zinc-500">Monitor personal DMs and servers consolidated</p>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        discordPref?.connected ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-900/30' : 'bg-zinc-900 text-zinc-500'
                      }`}>
                        {discordPref?.connected ? 'Active' : 'Offline'}
                      </span>
                    </div>
                    {discordPref?.connected ? (
                      <button
                        onClick={() => disconnectMutation.mutate('discord')}
                        className="w-full text-center py-2 bg-zinc-950 hover:bg-red-950/20 hover:text-red-400 rounded text-xs font-semibold text-zinc-400 border border-zinc-850 hover:border-red-900/20 transition-all cursor-pointer"
                      >
                        Disconnect Discord
                      </button>
                    ) : (
                      <button
                        onClick={handleConnectDiscord}
                        disabled={isDiscordConnecting}
                        className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white rounded-lg flex items-center justify-center gap-2 border border-indigo-500 hover:border-indigo-400 transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isDiscordConnecting ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Connecting Discord...
                          </>
                        ) : (
                          <>
                            Connect with Discord
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              )}

            </div>
          </div>

        </div>

      </div>
    </SidebarLayout>
  );
}
