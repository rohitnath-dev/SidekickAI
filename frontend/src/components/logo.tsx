import React from 'react';
import { BRANDING } from '@/config/branding';

interface LogoProps {
  className?: string;
  size?: number;
}

export default function Logo({ className = '', size = 32 }: LogoProps) {
  return (
    <div className={`flex items-center gap-2 select-none font-semibold ${className}`}>
      <img
        src={BRANDING.canonicalLogoPath}
        alt={`${BRANDING.name} Logo`}
        width={size}
        height={size}
        className="transition-transform duration-300 hover:rotate-12 rounded-lg"
        style={{ width: size, height: size, objectFit: 'contain' }}
      />
      <span className="tracking-tight text-zinc-100" style={{ fontSize: `${size * 0.6}px` }}>
        {BRANDING.nameFormatted}<span className="text-zinc-400 font-normal">{BRANDING.nameSuffix}</span>
      </span>
    </div>
  );
}
