import React from 'react';
import { motion } from 'framer-motion';
import { Calendar, Clock, ArrowRight, Sparkles, ShieldCheck } from 'lucide-react';
import type { Workshop } from '../types';

interface HeroProps {
  workshop?: Workshop | null;
  onReserveClick: () => void;
  onLearnMoreClick: () => void;
}

export const Hero: React.FC<HeroProps> = ({
  workshop,
  onReserveClick,
  onLearnMoreClick,
}) => {
  // Format date and time if available from backend, else fallbacks
  const displayDate = workshop?.scheduled_at
    ? new Date(workshop.scheduled_at).toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : '18 September 2026';

  const displayTime = workshop?.scheduled_at
    ? new Date(workshop.scheduled_at).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      })
    : '3:30 PM';

  const displayTimezone = workshop?.timezone || 'Asia/Kolkata';

  return (
    <section className="relative pt-28 pb-16 sm:pt-36 sm:pb-24 overflow-hidden" aria-labelledby="hero-heading">
      {/* Subtle background ambient glows */}
      <div 
        className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] sm:w-[750px] h-[350px] sm:h-[450px] bg-gradient-to-tr from-indigo-600/15 via-purple-600/10 to-transparent blur-[120px] pointer-events-none -z-10" 
        aria-hidden="true" 
      />
      <div 
        className="absolute top-1/3 -right-20 w-[300px] h-[300px] bg-violet-600/10 blur-[100px] pointer-events-none -z-10" 
        aria-hidden="true" 
      />

      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Headlines & CTA */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="lg:col-span-7 text-left space-y-6 sm:space-y-8"
          >
            {/* Live Masterclass Tag */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs sm:text-sm font-medium">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>Public Speaking Workshop &bull; Live Session</span>
            </div>

            {/* Main Headline (Single h1) */}
            <div className="space-y-3">
              <h1
                id="hero-heading"
                className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.08]"
              >
                SPEAK <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 via-indigo-100 to-purple-200">
                  WITH CONFIDENCE.
                </span>
              </h1>
              <p className="text-xl sm:text-2xl font-medium text-indigo-200/90 tracking-tight">
                Be heard. Be remembered.
              </p>
            </div>

            {/* Description */}
            <p className="text-base sm:text-lg text-gray-300/90 max-w-xl leading-relaxed">
              A focused workshop designed to help you communicate with greater
              confidence, clarity, and impact in any room, meeting, or stage.
            </p>

            {/* Date / Time Card Pill */}
            <div className="flex flex-wrap items-center gap-4 py-2 text-sm text-gray-300">
              <div className="flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] px-3.5 py-2 rounded-xl backdrop-blur-sm">
                <Calendar className="w-4 h-4 text-indigo-400" />
                <span className="font-semibold text-white">{displayDate}</span>
              </div>
              <div className="flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] px-3.5 py-2 rounded-xl backdrop-blur-sm">
                <Clock className="w-4 h-4 text-purple-400" />
                <span className="font-semibold text-white">{displayTime}</span>
                <span className="text-gray-400 text-xs uppercase tracking-wider">{displayTimezone}</span>
              </div>
            </div>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-2">
              <button
                onClick={onReserveClick}
                className="inline-flex items-center justify-center gap-2.5 px-7 py-3.5 text-base font-semibold text-white transition-all duration-200 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl shadow-xl shadow-indigo-600/25 hover:shadow-indigo-600/40 hover:-translate-y-0.5 active:translate-y-0 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                <span>RESERVE YOUR SEAT</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={onLearnMoreClick}
                className="inline-flex items-center justify-center px-6 py-3.5 text-base font-medium text-gray-300 hover:text-white transition-colors bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.08] rounded-xl cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
              >
                Learn More
              </button>
            </div>

            {/* Micro reassurance */}
            <div className="flex items-center gap-2 text-xs text-gray-400 pt-1">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Instant confirmation via WhatsApp & Email &bull; 15-min reminder</span>
            </div>
          </motion.div>

          {/* Right Column: Abstract visual & cinematic presence */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="lg:col-span-5 relative flex items-center justify-center"
            aria-hidden="true"
          >
            <div className="relative w-72 h-72 sm:w-96 sm:h-96 flex items-center justify-center">
              {/* Outer pulsing rings */}
              <div className="absolute inset-0 rounded-full border border-indigo-500/20 animate-[spin_40s_linear_infinite]" />
              <div className="absolute inset-6 rounded-full border border-purple-500/20 animate-[spin_25s_linear_infinite_reverse]" />
              <div className="absolute inset-14 rounded-full border border-dashed border-indigo-400/25" />

              {/* Glowing Center Core */}
              <div className="w-44 h-44 sm:w-56 sm:h-56 rounded-full bg-gradient-to-tr from-indigo-600/30 via-purple-600/20 to-blue-500/20 backdrop-blur-2xl border border-white/10 shadow-[0_0_80px_rgba(99,102,241,0.25)] flex flex-col items-center justify-center text-center p-6 space-y-2">
                <div className="w-12 h-12 rounded-full bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center">
                  <div className="flex items-end gap-1 h-5">
                    <span className="w-1 bg-indigo-400 rounded-full animate-[pulse_1.2s_ease-in-out_infinite] h-3" />
                    <span className="w-1 bg-indigo-300 rounded-full animate-[pulse_1.5s_ease-in-out_infinite_0.2s] h-5" />
                    <span className="w-1 bg-purple-400 rounded-full animate-[pulse_1.1s_ease-in-out_infinite_0.4s] h-4" />
                    <span className="w-1 bg-indigo-400 rounded-full animate-[pulse_1.3s_ease-in-out_infinite_0.1s] h-2" />
                  </div>
                </div>
                <div className="text-xs font-bold tracking-widest text-indigo-300 uppercase">
                  Voice & Impact
                </div>
                <div className="text-[11px] text-gray-400 leading-tight">
                  Clarity &bull; Presence &bull; Command
                </div>
              </div>

              {/* Floating badges around orb */}
              <div className="absolute -top-2 right-4 bg-[#12141f]/90 border border-white/10 px-3.5 py-1.5 rounded-full text-xs font-medium text-gray-200 shadow-xl backdrop-blur-md">
                🎯 100% Actionable
              </div>
              <div className="absolute -bottom-2 left-4 bg-[#12141f]/90 border border-white/10 px-3.5 py-1.5 rounded-full text-xs font-medium text-gray-200 shadow-xl backdrop-blur-md">
                ⚡ Practical Frameworks
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};
