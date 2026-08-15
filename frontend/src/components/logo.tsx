import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
}

export default function Logo({
  className = '',
  size = 32,
}: LogoProps) {
  return (
    <div
      className={`flex items-center gap-2 select-none font-semibold ${className}`}
    >
      <img
        src="/logo.png"
        alt="SidekickAI"
        width={size}
        height={size}
        className="object-contain"
      />

      <span
        className="tracking-tight text-zinc-100"
        style={{ fontSize: `${size * 0.6}px` }}
      >
        Sidekick<span className="text-zinc-400 font-normal">AI</span>
      </span>
    </div>
  );
}
