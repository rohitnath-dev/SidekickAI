'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import { 
  LayoutDashboard, 
  Inbox, 
  MessageSquare, 
  CalendarDays, 
  BrainCircuit, 
  Settings, 
  LogOut,
  Menu,
  X,
  User,
  Activity
} from 'lucide-react';
import Logo from './logo';

interface SidebarProps {
  children: React.ReactNode;
}

export default function SidebarLayout({ children }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isMounted, setIsMounted] = useState<boolean>(false);

  useEffect(() => {
    setIsMounted(true);
    
    // Handle potential CJS/ESM import differences safely
    const c = (Cookies as any).default || Cookies;
    const token = typeof c.get === 'function' ? c.get('access_token') : undefined;

    if (!token) {
      setIsAuthenticated(false);
      router.push('/login');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  // SSR / Hydration Fallback: Render static loading screen matching the server DOM exactly
  if (!isMounted) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-950 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 tech-grid pointer-events-none opacity-40"></div>
        {/* Glowing Ambient Spot */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[25rem] h-[25rem] rounded-full bg-indigo-500/10 blur-[100px] animate-pulse"></div>
        
        <div className="relative z-10 flex flex-col items-center">
          <Logo size={48} className="animate-pulse" />
          <p className="mt-4 text-xs font-mono text-zinc-500 tracking-widest uppercase animate-pulse">Initializing assistant</p>
        </div>
      </div>
    );
  }

  // Once mounted, if not authenticated, render blank white transitioning/redirecting
  if (!isAuthenticated) {
    return null;
  }

  const navItems = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Inbox', href: '/inbox', icon: Inbox },
    { name: 'Direct Messages', href: '/messages', icon: MessageSquare },
    { name: 'AI Planner', href: '/planner', icon: CalendarDays },
    { name: 'Long-term Memory', href: '/memory', icon: BrainCircuit },
    { name: 'Settings & Integrations', href: '/settings', icon: Settings },
  ];

  const handleLogout = () => {
    const c = (Cookies as any).default || Cookies;
    if (typeof c.remove === 'function') {
      c.remove('access_token');
    }
    router.push('/login');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 font-sans relative">
      {/* Technology grid overlay */}
      <div className="tech-grid"></div>

      {/* Futuristic Floating Ambient Light Blobs */}
      <div className="glowing-blob-container">
        <div className="glowing-blob blob-purple animate-blob-1 -top-20 -left-20"></div>
        <div className="glowing-blob blob-blue animate-blob-2 -bottom-40 -right-20"></div>
        <div className="glowing-blob blob-cyan animate-blob-3 top-1/3 left-1/3"></div>
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col border-r border-zinc-900/60 bg-zinc-950/40 backdrop-blur-md p-6 justify-between select-none z-10">
        <div className="flex flex-col gap-8">
          <Link href="/" className="inline-block">
            <Logo size={28} />
          </Link>
          
          <nav className="flex flex-col gap-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 relative group border ${
                    isActive 
                      ? 'bg-indigo-500/10 text-zinc-50 border-indigo-500/20 shadow-sm shadow-indigo-500/5' 
                      : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/40 border-transparent hover:border-zinc-800/50'
                  }`}
                >
                  {/* Left indicator glow for active page */}
                  {isActive && (
                    <span className="absolute left-0 top-1/4 bottom-1/4 w-1 rounded-r-md bg-indigo-500 shadow-md shadow-indigo-400"></span>
                  )}
                  <Icon className={`w-4 h-4 transition-transform duration-300 group-hover:scale-110 ${isActive ? 'text-indigo-400' : 'text-zinc-400 group-hover:text-zinc-200'}`} />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>

        <button 
          onClick={handleLogout}
          className="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-rose-450 hover:bg-rose-950/15 transition-all duration-300 border border-transparent hover:border-rose-900/30 cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </aside>

      {/* Mobile Header & Overlay Menu */}
      <div className="flex flex-col flex-1 h-full overflow-hidden z-10 bg-transparent">
        <header className="flex items-center justify-between px-6 py-4 md:hidden border-b border-zinc-900/60 bg-zinc-950/40 backdrop-blur-md z-20">
          <Link href="/">
            <Logo size={24} />
          </Link>
          <button 
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="p-1 text-zinc-400 hover:text-zinc-100 focus:outline-none"
          >
            {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </header>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div className="fixed inset-0 bg-zinc-950/90 backdrop-blur-xl z-10 flex flex-col p-6 pt-20 justify-between md:hidden">
            <nav className="flex flex-col gap-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`flex items-center gap-4 px-4 py-3 rounded-lg text-base font-medium transition-all duration-300 border ${
                      isActive 
                        ? 'bg-indigo-500/10 text-zinc-50 border-indigo-500/20' 
                        : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/40 border-transparent hover:border-zinc-800/50'
                    }`}
                  >
                    <Icon className={`w-5 h-5 ${isActive ? 'text-indigo-400' : 'text-zinc-400'}`} />
                    {item.name}
                  </Link>
                );
              })}
            </nav>

            <button 
              onClick={handleLogout}
              className="flex items-center gap-4 px-4 py-3 rounded-lg text-base font-medium text-zinc-400 hover:text-rose-450 hover:bg-rose-950/20 transition-all border border-transparent hover:border-rose-900/30 cursor-pointer"
            >
              <LogOut className="w-5 h-5" />
              Logout
            </button>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto bg-transparent focus:outline-none">
          {children}
        </main>
      </div>
    </div>
  );
}
