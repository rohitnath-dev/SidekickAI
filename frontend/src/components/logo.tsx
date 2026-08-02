import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
}

export default function Logo({ className = '', size = 32 }: LogoProps) {
  return (
    <div className={`flex items-center gap-2 select-none font-semibold ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="text-zinc-100 transition-transform duration-300 hover:rotate-12"
      >
        {/* Outer Ring */}
        <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="1.5" strokeDasharray="6 3" className="opacity-40" />
        
        {/* Inner Orbital Path */}
        <path
          d="M 6.5,20 A 13.5,13.5 0 1,0 33.5,20 A 13.5,13.5 0 1,0 6.5,20"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className="opacity-70"
        />
        
        {/* Core Node */}
        <circle cx="20" cy="20" r="4.5" fill="currentColor" />
        
        {/* Outer Orbiting Satellite */}
        <circle cx="31" cy="11" r="2.5" fill="currentColor" className="animate-pulse" />
      </svg>
      <span className="tracking-tight text-zinc-100" style={{ fontSize: `${size * 0.6}px` }}>
        Sidekick<span className="text-zinc-400 font-normal">AI</span>
      </span>
    </div>
  );
}
