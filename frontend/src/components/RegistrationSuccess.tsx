import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Mail, MessageSquare, Bell, Calendar, User, ArrowLeft } from 'lucide-react';
import type { RegistrationResponse } from '../types';

interface RegistrationSuccessProps {
  response: RegistrationResponse;
  isNew: boolean;
  onReset: () => void;
}

export const RegistrationSuccess: React.FC<RegistrationSuccessProps> = ({
  response,
  isNew,
  onReset,
}) => {
  const workshop = response.workshop;
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

  const timezone = workshop?.timezone || 'Asia/Kolkata';

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="p-8 sm:p-10 rounded-3xl bg-[#121422] border border-indigo-500/30 shadow-2xl relative overflow-hidden text-center space-y-8 max-w-xl mx-auto"
      role="status"
      aria-live="polite"
    >
      {/* Background glow */}
      <div 
        className="absolute -top-24 left-1/2 -translate-x-1/2 w-80 h-80 bg-gradient-to-b from-indigo-500/20 to-transparent blur-3xl pointer-events-none" 
        aria-hidden="true" 
      />

      {/* Checkmark animation */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.1 }}
        className="w-20 h-20 mx-auto rounded-full bg-emerald-500/15 border-2 border-emerald-500/40 flex items-center justify-center text-emerald-400 shadow-[0_0_40px_rgba(16,185,129,0.25)]"
      >
        <CheckCircle2 className="w-10 h-10 text-emerald-400" />
      </motion.div>

      {/* Header */}
      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-emerald-400">
          {isNew ? "Seat Confirmed" : "Registration Confirmed"}
        </span>
        <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          {isNew ? "YOU'RE REGISTERED!" : "YOU'RE ALREADY REGISTERED!"}
        </h3>
        <p className="text-sm sm:text-base text-gray-300">
          {response.message || 'Your place in the workshop has been secured.'}
        </p>
      </div>

      {/* Registration & Session Details Card */}
      <div className="rounded-2xl bg-black/30 border border-white/[0.08] p-5 sm:p-6 text-left space-y-4">
        <div className="flex items-center gap-3 pb-3 border-b border-white/[0.06]">
          <User className="w-4 h-4 text-indigo-400" />
          <div className="text-sm">
            <span className="text-gray-400 text-xs block">Attendee</span>
            <strong className="text-white font-semibold">{response.full_name}</strong>
          </div>
        </div>

        <div className="flex items-center gap-3 pb-3 border-b border-white/[0.06]">
          <Calendar className="w-4 h-4 text-indigo-400" />
          <div className="text-sm">
            <span className="text-gray-400 text-xs block">{workshop?.title || 'Public Speaking Workshop'}</span>
            <strong className="text-white font-semibold">
              {displayDate} &bull; {displayTime} ({timezone})
            </strong>
          </div>
        </div>

        {/* Channels */}
        <div className="pt-1 space-y-2">
          <span className="text-xs font-semibold text-gray-400 block uppercase tracking-wider">
            Your confirmation has been sent via:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] text-xs text-gray-200">
              <Mail className="w-4 h-4 text-indigo-400 shrink-0" />
              <span className="truncate">{response.email}</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] text-xs text-gray-200">
              <MessageSquare className="w-4 h-4 text-emerald-400 shrink-0" />
              <span className="truncate">{response.phone_number}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 15-Minute reminder callout */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-left">
        <Bell className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <p className="text-xs sm:text-sm text-indigo-200 leading-relaxed">
          <strong>Automatic Reminder:</strong> You will receive a reminder via WhatsApp and Email <strong>15 minutes before</strong> the workshop starts with joining instructions.
        </p>
      </div>

      {/* Return CTA */}
      <div className="pt-2">
        <button
          onClick={onReset}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-sm font-semibold text-white transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>BACK TO WORKSHOP</span>
        </button>
      </div>
    </motion.div>
  );
};
