import React from 'react';
import { Calendar, Clock, Bell, Video } from 'lucide-react';
import type { Workshop } from '../types';

interface WorkshopInfoProps {
  workshop?: Workshop | null;
}

export const WorkshopInfo: React.FC<WorkshopInfoProps> = ({ workshop }) => {
  const displayDate = workshop?.scheduled_at
    ? new Date(workshop.scheduled_at).toLocaleDateString('en-GB', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : 'Friday, 18 September 2026';

  const displayTime = workshop?.scheduled_at
    ? new Date(workshop.scheduled_at).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      })
    : '3:30 PM';

  const timezone = workshop?.timezone || 'Asia/Kolkata';
  const reminderMinutes = workshop?.reminder_lead_minutes || 15;

  return (
    <section id="workshop-info" className="py-16 sm:py-24 bg-[#0d0f1a]/80 border-t border-white/[0.06]" aria-labelledby="info-heading">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="text-center max-w-xl mx-auto mb-12 space-y-3">
          <span className="text-xs font-bold uppercase tracking-widest text-indigo-400">
            Session Details
          </span>
          <h2
            id="info-heading"
            className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight"
          >
            Workshop Overview
          </h2>
          <p className="text-base text-gray-400">
            Everything you need to know about the scheduled session.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Date Card */}
          <div className="p-6 rounded-2xl bg-[#121422] border border-white/[0.08] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 block">
                Date
              </span>
              <span className="text-lg font-bold text-white mt-1 block">
                {displayDate}
              </span>
            </div>
          </div>

          {/* Time Card */}
          <div className="p-6 rounded-2xl bg-[#121422] border border-white/[0.08] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 block">
                Time
              </span>
              <span className="text-lg font-bold text-white mt-1 block">
                {displayTime}{' '}
                <span className="text-xs font-normal text-gray-400">({timezone})</span>
              </span>
            </div>
          </div>

          {/* Automated Reminder Card */}
          <div className="p-6 rounded-2xl bg-[#121422] border border-white/[0.08] space-y-3 sm:col-span-2 lg:col-span-1">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 block">
                Automated Reminder
              </span>
              <span className="text-lg font-bold text-white mt-1 block">
                {reminderMinutes} Minutes Before Start
              </span>
              <span className="text-xs text-gray-400 block mt-0.5">
                Sent to Email & WhatsApp
              </span>
            </div>
          </div>

          {/* Optional Meeting Link Card - Only if backend provides it */}
          {workshop?.meeting_link && (
            <div className="p-6 rounded-2xl bg-[#121422] border border-indigo-500/20 space-y-3 sm:col-span-2 lg:col-span-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <Video className="w-5 h-5" />
              </div>
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 block">
                  Online Access
                </span>
                <a
                  href={workshop.meeting_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-base font-semibold text-indigo-400 hover:text-indigo-300 underline underline-offset-4 mt-1 inline-block"
                >
                  Join Meeting URL
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
