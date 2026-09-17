import React from 'react';
import { Mic, Shield } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="py-12 border-t border-white/[0.06] bg-[#07080d] text-gray-400 text-xs sm:text-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Mic className="w-3.5 h-3.5" />
          </div>
          <span className="font-bold text-white tracking-tight">
            Public Speaking Workshop
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Shield className="w-3.5 h-3.5 text-indigo-400" />
          <span>Your contact information is strictly used for workshop notifications.</span>
        </div>

        <div className="text-gray-500 text-xs">
          &copy; {new Date().getFullYear()} Public Speaking Workshop. All rights reserved.
        </div>
      </div>
    </footer>
  );
};
