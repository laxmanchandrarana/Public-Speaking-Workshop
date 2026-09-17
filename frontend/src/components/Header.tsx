import React from 'react';
import { Mic } from 'lucide-react';

interface HeaderProps {
  onReserveClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onReserveClick }) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 transition-all duration-300 bg-[#090a10]/80 backdrop-blur-md border-b border-white/[0.06]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 sm:h-20 flex items-center justify-between">
        {/* Brand */}
        <a 
          href="#" 
          className="flex items-center gap-2.5 sm:gap-3 group text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded-lg p-1"
        >
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 group-hover:border-indigo-400/50 transition-colors">
            <Mic className="w-5 h-5 text-indigo-400 group-hover:scale-110 transition-transform duration-300" />
          </div>
          <div>
            <span className="text-sm sm:text-base font-bold tracking-tight text-white block">
              Public Speaking Workshop
            </span>
            <span className="text-[11px] text-gray-400 font-medium tracking-wide hidden sm:block">
              Exclusive Live Masterclass
            </span>
          </div>
        </a>

        {/* Action Button */}
        <button
          onClick={onReserveClick}
          className="relative inline-flex items-center justify-center px-4 sm:px-5 py-2 sm:py-2.5 text-xs sm:text-sm font-semibold text-white transition-all duration-200 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 rounded-full shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/40 hover:-translate-y-0.5 active:translate-y-0 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-500"
        >
          <span>Reserve Your Seat</span>
        </button>
      </div>
    </header>
  );
};
