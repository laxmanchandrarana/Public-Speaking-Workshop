import React from 'react';
import { useCountdown } from '../hooks/useCountdown';
import { Clock, Radio } from 'lucide-react';

interface CountdownProps {
  scheduledAt?: string;
  timezone?: string;
}

export const Countdown: React.FC<CountdownProps> = ({ scheduledAt, timezone = 'Asia/Kolkata' }) => {
  const { days, hours, minutes, seconds, isLive, isCompleted, isStarted } = useCountdown(scheduledAt);

  const pad = (n: number) => String(n).padStart(2, '0');

  return (
    <section className="py-10 border-y border-white/[0.06] bg-white/[0.01]" aria-label="Workshop Countdown">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
        {/* State: In Progress / Live */}
        {isLive && (
          <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-300 font-bold tracking-wider text-sm uppercase animate-pulse">
            <Radio className="w-4 h-4 text-rose-400" />
            <span>WORKSHOP IS LIVE NOW</span>
          </div>
        )}

        {/* State: Completed */}
        {isCompleted && (
          <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gray-500/10 border border-gray-500/30 text-gray-300 font-bold tracking-wider text-sm uppercase">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>WORKSHOP HAS STARTED</span>
          </div>
        )}

        {/* State: Active Countdown */}
        {!isStarted && (
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest text-indigo-400 uppercase">
              <Clock className="w-3.5 h-3.5" />
              <span>Event Starts In ({timezone})</span>
            </div>

            <div className="grid grid-cols-4 gap-2 sm:gap-4 max-w-xl mx-auto">
              {/* Days */}
              <div className="bg-[#10121d] border border-white/[0.08] rounded-2xl p-3 sm:p-5 flex flex-col items-center justify-center shadow-lg">
                <span className="font-mono text-2xl sm:text-4xl md:text-5xl font-extrabold text-white tracking-tight">
                  {pad(days)}
                </span>
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-gray-400 mt-1">
                  Days
                </span>
              </div>

              {/* Hours */}
              <div className="bg-[#10121d] border border-white/[0.08] rounded-2xl p-3 sm:p-5 flex flex-col items-center justify-center shadow-lg">
                <span className="font-mono text-2xl sm:text-4xl md:text-5xl font-extrabold text-white tracking-tight">
                  {pad(hours)}
                </span>
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-gray-400 mt-1">
                  Hours
                </span>
              </div>

              {/* Minutes */}
              <div className="bg-[#10121d] border border-white/[0.08] rounded-2xl p-3 sm:p-5 flex flex-col items-center justify-center shadow-lg">
                <span className="font-mono text-2xl sm:text-4xl md:text-5xl font-extrabold text-white tracking-tight">
                  {pad(minutes)}
                </span>
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-gray-400 mt-1">
                  Minutes
                </span>
              </div>

              {/* Seconds */}
              <div className="bg-[#10121d] border border-white/[0.08] rounded-2xl p-3 sm:p-5 flex flex-col items-center justify-center shadow-lg border-indigo-500/20">
                <span className="font-mono text-2xl sm:text-4xl md:text-5xl font-extrabold text-indigo-300 tracking-tight">
                  {pad(seconds)}
                </span>
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-indigo-400/80 mt-1">
                  Seconds
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
