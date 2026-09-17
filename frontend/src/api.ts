import type { Workshop, RegistrationRequest, RegistrationResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  status: number;
  fieldErrors?: Record<string, string[]>;
  code?: string;

  constructor(message: string, status: number, fieldErrors?: Record<string, string[]>, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.code = code;
  }
}

/**
 * Fetch active workshop details from Django backend
 */
export async function fetchWorkshop(): Promise<Workshop> {
  const url = `${API_BASE_URL}/api/v1/workshop/`;
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      throw new ApiError('Failed to load workshop details', res.status);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Request timed out while loading workshop data.', 408);
    }
    throw new ApiError('Unable to connect to workshop service. Please check your internet connection.', 0);
  }
}

/**
 * Register attendee with strict idempotency key
 */
export async function registerAttendee(
  data: RegistrationRequest,
  idempotencyKey: string
): Promise<{ data: RegistrationResponse; isNew: boolean }> {
  const url = `${API_BASE_URL}/api/v1/registrations/`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const json = await res.json().catch(() => null);

    if (!res.ok) {
      if (res.status === 400 && json && typeof json === 'object') {
        if ('error' in json && typeof json.error === 'string') {
          throw new ApiError(json.error, 400);
        }
        // Field validation errors: e.g. { full_name: [...], email: [...] }
        const fieldErrors: Record<string, string[]> = {};
        for (const [key, val] of Object.entries(json)) {
          if (Array.isArray(val)) {
            fieldErrors[key] = val.map(String);
          } else if (typeof val === 'string') {
            fieldErrors[key] = [val];
          }
        }
        const firstMsg = Object.values(fieldErrors)[0]?.[0] || 'Invalid registration details.';
        throw new ApiError(firstMsg, 400, fieldErrors);
      }

      if (res.status === 409) {
        const msg = json?.error || 'A registration request with these details is already being processed.';
        throw new ApiError(msg, 409, undefined, json?.code || 'idempotency_conflict');
      }

      if (res.status === 429) {
        throw new ApiError('Too many attempts. Please wait a moment and try again.', 429);
      }

      if (res.status >= 500) {
        throw new ApiError("We couldn't complete your registration right now. Please try again in a few moments.", res.status);
      }

      throw new ApiError(json?.error || 'Registration failed. Please review your details and try again.', res.status);
    }

    // 201 = Created fresh registration, 200 = Existing duplicate / idempotent confirmation
    const isNew = res.status === 201;
    return { data: json as RegistrationResponse, isNew };
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Registration request timed out. Please verify your connection and try again.', 408);
    }
    throw new ApiError('Network connection issue. Please check your internet connection and try again.', 0);
  }
}
