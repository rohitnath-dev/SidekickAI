'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as zod from 'zod';
import Cookies from 'js-cookie';
import { ArrowRight, Lock, Mail, AlertCircle, Loader2 } from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';

const loginSchema = zod.object({
  email: zod.string().email({ message: 'Invalid email address' }),
  password: zod.string().min(1, { message: 'Password is required' }),
});

type LoginSchema = zod.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginSchema>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginSchema) => {
    setIsLoading(true);
    setError(null);

    try {
      // FastAPI OAuth2PasswordRequestForm expects form-urlencoded username and password
      const params = new URLSearchParams();
      params.append('username', data.email);
      params.append('password', data.password);
      const response = await apiClient.post('/auth/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      
      // SAVE TOKEN TO LOCALSTORAGE — this is the critical missing piece
      if (response.data?.access_token) {
        try {
          localStorage.setItem('access_token', response.data.access_token);
        } catch (e) {
          console.warn('Failed to save access token to localStorage:', e);
        }
      }
      
      router.push('/');
    } catch (err: any) {
      console.error(err);
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        const messages = detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
        setError(messages || 'Validation failed. Please check your credentials.');
      } else if (detail && typeof detail === 'object') {
        setError(detail.message || JSON.stringify(detail));
      } else if (err.message) {
        setError(err.message);
      } else {
        setError('Connection failed. Please check your credentials or backend server.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col justify-between bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8">
      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-md space-y-8">
          <div className="flex flex-col items-center justify-center text-center">
            <Logo size={40} className="mb-2" />
            <h2 className="mt-6 text-2xl font-bold tracking-tight text-zinc-100">
              Sign in to your account
            </h2>
            <p className="mt-3 text-sm text-zinc-400 leading-relaxed max-w-sm">
              SidekickAI: Your AI executive assistant for smart inbox management, automated tasks, and daily planning.
            </p>
            <p className="mt-4 text-xs text-zinc-500">
              Or{' '}
              <Link 
                href="/register" 
                className="font-medium text-zinc-300 hover:text-zinc-100 underline decoration-zinc-700 hover:decoration-zinc-400 transition-all animate-pulse"
              >
                create a new assistant profile
              </Link>
            </p>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 shadow-2xl backdrop-blur-md">
            {error && (
              <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-sm text-red-400">
                <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
                <div>
                  <h3 className="font-semibold">Authentication Error</h3>
                  <p className="mt-1">{error}</p>
                </div>
              </div>
            )}

            <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
              <div className="space-y-2">
                <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Email address
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <Mail className="h-4 w-4 text-zinc-500" />
                  </div>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    {...register('email')}
                    className="block w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition-all"
                    placeholder="name@example.com"
                  />
                </div>
                {errors.email && (
                  <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Password
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <Lock className="h-4 w-4 text-zinc-500" />
                  </div>
                  <input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    {...register('password')}
                    className="block w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition-all"
                    placeholder="••••••••"
                  />
                </div>
                {errors.password && (
                  <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>
                )}
              </div>

              <div>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-semibold text-zinc-950 hover:bg-zinc-200 focus:outline-none transition-all disabled:opacity-50 disabled:hover:bg-zinc-100 cursor-pointer shadow-md"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      Sign In
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <footer className="w-full text-center text-xs text-zinc-500 border-t border-zinc-900/40 pt-6 mt-8">
        <div className="flex justify-center gap-6 mb-3">
          <Link href="/privacy" className="hover:text-zinc-300 transition-colors">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-zinc-300 transition-colors">
            Terms of Service
          </Link>
        </div>
        <p>&copy; {new Date().getFullYear()} SidekickAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
