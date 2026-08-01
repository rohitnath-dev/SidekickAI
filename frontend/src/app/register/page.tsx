'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as zod from 'zod';
import Cookies from 'js-cookie';
import { ArrowRight, Lock, Mail, User, AlertCircle, Loader2 } from 'lucide-react';
import Logo from '@/components/logo';
import { apiClient } from '@/lib/api-client';

const registerSchema = zod.object({
  fullName: zod.string().min(1, { message: 'Full name is required' }),
  email: zod.string().email({ message: 'Invalid email address' }),
  password: zod.string().min(8, { message: 'Password must be at least 8 characters' }),
});

type RegisterSchema = zod.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterSchema>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterSchema) => {
    setIsLoading(true);
    setError(null);

    try {
      // Backend expects: email, password, full_name in JSON body
      const response = await apiClient.post('/auth/register', {
        email: data.email,
        password: data.password,
        full_name: data.fullName,
      });

      const { access_token } = response.data;
      
      // Store token in cookies for OAuth redirect support
      Cookies.set('access_token', access_token, { expires: 7, sameSite: 'lax' });
      
      router.push('/');
    } catch (err: any) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Registration failed. Please try again or check backend server.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center justify-center text-center">
          <Logo size={40} className="mb-2" />
          <h2 className="mt-6 text-2xl font-bold tracking-tight text-zinc-100">
            Create your assistant profile
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Or{' '}
            <Link 
              href="/login" 
              className="font-medium text-zinc-300 hover:text-zinc-100 underline decoration-zinc-700 hover:decoration-zinc-400 transition-all"
            >
              sign in to your existing account
            </Link>
          </p>
        </div>

        <div className="bg-zinc-900/40 border border-zinc-900 rounded-xl p-6 shadow-2xl backdrop-blur-md">
          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-sm text-red-400">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
              <div>
                <h3 className="font-semibold">Registration Error</h3>
                <p className="mt-1">{error}</p>
              </div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-2">
              <label htmlFor="fullName" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Full Name
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <User className="h-4 w-4 text-zinc-500" />
                </div>
                <input
                  id="fullName"
                  type="text"
                  {...register('fullName')}
                  className="block w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition-all"
                  placeholder="John Doe"
                />
              </div>
              {errors.fullName && (
                <p className="text-xs text-red-400 mt-1">{errors.fullName.message}</p>
              )}
            </div>

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
                  autoComplete="new-password"
                  {...register('password')}
                  className="block w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition-all"
                  placeholder="•••••••• (min 8 chars)"
                />
              </div>
              {errors.password && (
                <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>
              )}
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-semibold text-zinc-950 hover:bg-zinc-200 focus:outline-none transition-all disabled:opacity-50 disabled:hover:bg-zinc-100 cursor-pointer shadow-md"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating profile...
                  </>
                ) : (
                  <>
                    Sign Up
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
