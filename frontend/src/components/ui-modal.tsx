'use client';

import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import UIButton from './ui-button';

export interface UIModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

export const UIModal: React.FC<UIModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Accessible Backdrop Overlay */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Container */}
      <div
        className={`relative w-full ${maxWidthClasses[maxWidth]} bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl z-10 overflow-hidden animate-in zoom-in-95 duration-150 text-zinc-100 space-y-0`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-zinc-900 bg-zinc-900/30">
          <div className="space-y-1 pr-6">
            <h3 id="modal-title" className="text-base font-bold text-zinc-50 tracking-tight">
              {title}
            </h3>
            {description && (
              <p className="text-xs text-zinc-400 leading-relaxed">{description}</p>
            )}
          </div>

          {/* Accessible Dismiss Button */}
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all cursor-pointer shrink-0 border border-transparent hover:border-zinc-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 max-h-[75vh] overflow-y-auto space-y-4 text-xs text-zinc-300">
          {children}
        </div>

        {/* Optional Footer */}
        {footer && (
          <div className="p-4 bg-zinc-900/40 border-t border-zinc-900 flex items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

export default UIModal;
