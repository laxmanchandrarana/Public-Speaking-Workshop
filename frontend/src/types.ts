export interface Workshop {
  id: string;
  title: string;
  scheduled_at: string; // ISO-8601 string, e.g. "2026-09-18T15:30:00+05:30"
  timezone: string;
  reminder_lead_minutes: number;
  reminder_at: string; // ISO-8601 string, e.g. "2026-09-18T15:15:00+05:30"
  meeting_link: string | null;
  is_active: boolean;
}

export interface RegistrationRequest {
  full_name: string;
  email: string;
  phone_number: string;
}

export interface RegistrationResponse {
  registration_id: string;
  full_name: string;
  email: string;
  phone_number: string;
  workshop: {
    title: string;
    scheduled_at: string;
    timezone: string;
  };
  message: string;
}

export interface CountdownState {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  isStarted: boolean;
  isLive: boolean; // within 2 hours after scheduled_at
  isCompleted: boolean;
}

export type SubmissionStatus = 'IDLE' | 'SUBMITTING' | 'SUCCESS' | 'ERROR';
