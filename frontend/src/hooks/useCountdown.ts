import { useState, useEffect } from 'react';
import type { CountdownState } from '../types';

function getCountdownState(scheduledAtIso?: string): CountdownState {
  if (!scheduledAtIso) {
    return {
      days: 0,
      hours: 0,
      minutes: 0,
      seconds: 0,
      isStarted: false,
      isLive: false,
      isCompleted: false,
    };
  }

  const targetDate = new Date(scheduledAtIso).getTime();
  const now = Date.now();
  const diff = targetDate - now;

  // Workshop duration estimate (2 hours)
  const TWO_HOURS_MS = 2 * 60 * 60 * 1000;

  if (diff <= 0) {
    const isLive = Math.abs(diff) < TWO_HOURS_MS;
    return {
      days: 0,
      hours: 0,
      minutes: 0,
      seconds: 0,
      isStarted: true,
      isLive,
      isCompleted: !isLive,
    };
  }

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  return {
    days: Math.max(0, days),
    hours: Math.max(0, hours),
    minutes: Math.max(0, minutes),
    seconds: Math.max(0, seconds),
    isStarted: false,
    isLive: false,
    isCompleted: false,
  };
}

export function useCountdown(scheduledAtIso?: string): CountdownState {
  const [state, setState] = useState<CountdownState>(() => getCountdownState(scheduledAtIso));

  useEffect(() => {
    const timer = setInterval(() => {
      setState(getCountdownState(scheduledAtIso));
    }, 1000);

    return () => clearInterval(timer);
  }, [scheduledAtIso]);

  return state;
}
