import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { User, Mail, Phone, CheckCircle2, AlertCircle, RefreshCw, Loader2, Sparkles } from 'lucide-react';
import type { RegistrationRequest, RegistrationResponse, SubmissionStatus } from '../types';
import { registerAttendee, ApiError } from '../api';

interface RegistrationFormProps {
  onSuccess: (response: RegistrationResponse, isNew: boolean) => void;
}

export const RegistrationForm: React.FC<RegistrationFormProps> = ({ onSuccess }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');

  // Frontend validation error states
  const [nameError, setNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  // Form submission state
  const [status, setStatus] = useState<SubmissionStatus>('IDLE');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Idempotency key tracking
  // Store the key for current submission attempt and reuse on retry
  const idempotencyKeyRef = useRef<string | null>(null);

  const validate = (): boolean => {
    let isValid = true;

    // Full name validation
    const trimmedName = fullName.trim();
    if (!trimmedName) {
      setNameError('Please enter your full name.');
      isValid = false;
    } else if (trimmedName.length < 2) {
      setNameError('Full name must be at least 2 characters.');
      isValid = false;
    } else {
      setNameError(null);
    }

    // Email validation
    const trimmedEmail = email.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!trimmedEmail) {
      setEmailError('Please enter your email address.');
      isValid = false;
    } else if (!emailRegex.test(trimmedEmail)) {
      setEmailError('Please enter a valid email address.');
      isValid = false;
    } else {
      setEmailError(null);
    }

    // Phone validation
    const trimmedPhone = phoneNumber.trim();
    // Allow digits, spaces, dashes, parentheses, with optional leading +
    const cleanDigits = trimmedPhone.replace(/\D/g, '');
    if (!trimmedPhone) {
      setPhoneError('Please enter your phone number.');
      isValid = false;
    } else if (cleanDigits.length < 7 || cleanDigits.length > 15) {
      setPhoneError('Please enter a valid phone number (e.g. +91 98765 43210).');
      isValid = false;
    } else {
      setPhoneError(null);
    }

    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent, isRetry = false) => {
    e.preventDefault();

    if (status === 'SUBMITTING') return; // Prevent double-click

    if (!validate()) return;

    // Maintain stable idempotency key on retry, or generate fresh for new deliberate submission
    if (!isRetry || !idempotencyKeyRef.current) {
      idempotencyKeyRef.current = typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `sub_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    }

    setStatus('SUBMITTING');
    setErrorMessage(null);

    const payload: RegistrationRequest = {
      full_name: fullName.trim(),
      email: email.trim(),
      phone_number: phoneNumber.trim(),
    };

    try {
      const result = await registerAttendee(payload, idempotencyKeyRef.current);
      setStatus('SUCCESS');
      onSuccess(result.data, result.isNew);
    } catch (err: unknown) {
      setStatus('ERROR');
      if (err instanceof ApiError) {
        if (err.fieldErrors) {
          if (err.fieldErrors.full_name) setNameError(err.fieldErrors.full_name[0]);
          if (err.fieldErrors.email) setEmailError(err.fieldErrors.email[0]);
          if (err.fieldErrors.phone_number) setPhoneError(err.fieldErrors.phone_number[0]);
        }
        setErrorMessage(err.message);
      } else {
        setErrorMessage('We could not complete your registration right now. Please try again.');
      }
    }
  };

  return (
    <div className="p-8 sm:p-10 rounded-3xl bg-[#121422]/90 border border-white/[0.09] shadow-2xl relative max-w-xl mx-auto backdrop-blur-xl">
      {/* Top subtle glow */}
      <div 
        className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-1 bg-gradient-to-r from-transparent via-indigo-500 to-transparent blur-[1px]" 
        aria-hidden="true" 
      />

      <div className="text-center space-y-2 mb-8">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold uppercase tracking-wider">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Limited Seats</span>
        </div>
        <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          RESERVE YOUR SEAT
        </h3>
        <p className="text-sm sm:text-base text-gray-300">
          Save your place and receive your workshop confirmation instantly.
        </p>
      </div>

      {/* Error Banner */}
      {status === 'ERROR' && errorMessage && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs sm:text-sm flex items-start gap-3 text-left"
          role="alert"
          aria-live="assertive"
        >
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-2">
            <p>{errorMessage}</p>
            <button
              type="button"
              onClick={(e) => handleSubmit(e, true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-semibold transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Registration</span>
            </button>
          </div>
        </motion.div>
      )}

      <form onSubmit={(e) => handleSubmit(e, false)} className="space-y-5 text-left" noValidate>
        {/* Full Name */}
        <div className="space-y-1.5">
          <label htmlFor="fullName" className="block text-xs font-semibold uppercase tracking-wider text-gray-300">
            Full Name <span className="text-rose-400" aria-hidden="true">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
              <User className="w-4 h-4" />
            </div>
            <input
              id="fullName"
              name="fullName"
              type="text"
              required
              autoComplete="name"
              disabled={status === 'SUBMITTING'}
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (nameError) setNameError(null);
                idempotencyKeyRef.current = null; // reset key on data change
              }}
              placeholder="e.g. Aarav Sharma"
              aria-invalid={!!nameError}
              aria-describedby={nameError ? 'name-error' : undefined}
              className={`w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.04] border ${
                nameError ? 'border-rose-500/60 focus:border-rose-500' : 'border-white/[0.1] focus:border-indigo-500'
              } text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
            />
          </div>
          {nameError && (
            <p id="name-error" className="text-xs text-rose-400 pl-1" role="alert">
              {nameError}
            </p>
          )}
        </div>

        {/* Phone Number */}
        <div className="space-y-1.5">
          <label htmlFor="phoneNumber" className="block text-xs font-semibold uppercase tracking-wider text-gray-300">
            Phone Number <span className="text-rose-400" aria-hidden="true">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
              <Phone className="w-4 h-4" />
            </div>
            <input
              id="phoneNumber"
              name="phoneNumber"
              type="tel"
              required
              autoComplete="tel"
              disabled={status === 'SUBMITTING'}
              value={phoneNumber}
              onChange={(e) => {
                setPhoneNumber(e.target.value);
                if (phoneError) setPhoneError(null);
                idempotencyKeyRef.current = null;
              }}
              placeholder="e.g. +91 98765 43210"
              aria-invalid={!!phoneError}
              aria-describedby={phoneError ? 'phone-error' : undefined}
              className={`w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.04] border ${
                phoneError ? 'border-rose-500/60 focus:border-rose-500' : 'border-white/[0.1] focus:border-indigo-500'
              } text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
            />
          </div>
          {phoneError && (
            <p id="phone-error" className="text-xs text-rose-400 pl-1" role="alert">
              {phoneError}
            </p>
          )}
        </div>

        {/* Email Address */}
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-gray-300">
            Email Address <span className="text-rose-400" aria-hidden="true">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
              <Mail className="w-4 h-4" />
            </div>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              disabled={status === 'SUBMITTING'}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailError) setEmailError(null);
                idempotencyKeyRef.current = null;
              }}
              placeholder="e.g. aarav@example.com"
              aria-invalid={!!emailError}
              aria-describedby={emailError ? 'email-error' : undefined}
              className={`w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.04] border ${
                emailError ? 'border-rose-500/60 focus:border-rose-500' : 'border-white/[0.1] focus:border-indigo-500'
              } text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
            />
          </div>
          {emailError && (
            <p id="email-error" className="text-xs text-rose-400 pl-1" role="alert">
              {emailError}
            </p>
          )}
        </div>

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={status === 'SUBMITTING'}
            className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 text-base font-bold text-white transition-all duration-200 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl shadow-xl shadow-indigo-600/30 hover:shadow-indigo-600/50 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            {status === 'SUBMITTING' ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>RESERVING YOUR SEAT...</span>
              </>
            ) : (
              <span>RESERVE MY SEAT</span>
            )}
          </button>
        </div>
      </form>

      {/* Micro assurances below form */}
      <div className="mt-6 pt-6 border-t border-white/[0.06] space-y-2 text-left">
        <div className="flex items-center gap-2 text-xs text-gray-300">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>Instant Email confirmation with calendar invite</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-300">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>WhatsApp confirmation sent right to your device</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-300">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>Automated reminder sent 15 minutes before the workshop</span>
        </div>
      </div>
    </div>
  );
};
