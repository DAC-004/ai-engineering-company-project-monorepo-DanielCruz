import type {
  Appointment,
  CareRequest,
  Clinic
} from '../types/models.js';
import {
  CLINIC_LOCATIONS,
  COMMUNICATION_CHANNELS,
  PAYMENT_MODELS,
  SERVICE_LINES,
  TIME_WINDOWS
} from '../types/models.js';

function findById<T extends { id: string }>(items: T[], id: string): T | null {
  const match = items.find((item) => item.id === id);
  return match ?? null;
}

export type ValidationResult = {
  valid: boolean;
  errors: string[];
};

function createValidationResult(errors: string[]): ValidationResult {
  return {
    valid: errors.length === 0,
    errors
  };
}

function parseIsoDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null;
  }

  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isAdult(dateOfBirth: string): boolean {
  const dob = parseIsoDate(dateOfBirth);
  if (!dob) {
    return false;
  }

  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();

  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age -= 1;
  }

  return age >= 18;
}

function isTodayOrFutureDate(dateString: string): boolean {
  const selected = parseIsoDate(dateString);
  if (!selected) {
    return false;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return selected >= today;
}

export function validateClinic(clinic: Clinic): ValidationResult {
  const errors: string[] = [];

  if (!clinic.id.trim()) {
    errors.push('Clinic id is required.');
  }

  if (!clinic.name.trim()) {
    errors.push('Clinic name is required.');
  }

  if (clinic.market_country !== 'US' && clinic.market_country !== 'UK') {
    errors.push('Clinic market_country must be US or UK.');
  } else if (!CLINIC_LOCATIONS[clinic.market_country].includes(clinic.name)) {
    errors.push('Clinic name must match an allowed location for the selected market_country.');
  }

  return createValidationResult(errors);
}

export function validateCareRequest(request: CareRequest): ValidationResult {
  const errors: string[] = [];

  if (!request.id.trim()) {
    errors.push('Care request id is required.');
  }

  if (!request.full_name) {
    errors.push('full_name is required.');
  } else if (!/^[A-Za-z\s'.-]{2,80}$/.test(request.full_name)) {
    errors.push('full_name must be 2-80 characters using letters and standard punctuation.');
  }

  if (!request.date_of_birth) {
    errors.push('date_of_birth is required.');
  } else if (!isAdult(request.date_of_birth)) {
    errors.push('Patient must be at least 18 years old.');
  }

  if (!request.email) {
    errors.push('email is required.');
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(request.email)) {
    errors.push('email must use a valid email format.');
  }

  if (!request.market_country) {
    errors.push('market_country is required.');
  }

  if (!request.phone) {
    errors.push('phone is required.');
  } else if (request.market_country === 'US' && !/^\+1\d{10}$/.test(request.phone)) {
    errors.push('phone must use +1 followed by 10 digits for US care requests.');
  } else if (request.market_country === 'UK' && !/^\+44\d{10}$/.test(request.phone)) {
    errors.push('phone must use +44 followed by 10 digits for UK care requests.');
  }

  if (!request.clinic_location) {
    errors.push('clinic_location is required.');
  } else if (
    request.market_country &&
    !CLINIC_LOCATIONS[request.market_country].includes(request.clinic_location)
  ) {
    errors.push('clinic_location must match the selected market_country.');
  }

  if (!request.service_line) {
    errors.push('service_line is required.');
  } else if (!SERVICE_LINES.includes(request.service_line)) {
    errors.push('service_line must be a supported HealthCore service line.');
  }

  if (!request.preferred_date) {
    errors.push('preferred_date is required.');
  } else if (!isTodayOrFutureDate(request.preferred_date)) {
    errors.push('preferred_date must be today or a future date.');
  }

  if (!request.preferred_time_window) {
    errors.push('preferred_time_window is required.');
  } else if (!TIME_WINDOWS.includes(request.preferred_time_window)) {
    errors.push('preferred_time_window must be a supported appointment window.');
  }

  if (!request.communication_channel) {
    errors.push('communication_channel is required.');
  } else if (!COMMUNICATION_CHANNELS.includes(request.communication_channel)) {
    errors.push('communication_channel must be SMS, Email, or Phone Call.');
  }

  if (!request.payment_model) {
    errors.push('payment_model is required.');
  } else if (
    request.market_country &&
    !PAYMENT_MODELS[request.market_country].includes(request.payment_model)
  ) {
    errors.push('payment_model must match the selected market_country.');
  }

  if (!request.member_identifier) {
    errors.push('member_identifier is required.');
  } else if (request.payment_model === 'NHS Contract (UK)' && !/^\d{10}$/.test(request.member_identifier)) {
    errors.push('member_identifier must contain exactly 10 digits for NHS Contract (UK).');
  } else if (
    request.payment_model !== 'NHS Contract (UK)' &&
    !/^[A-Za-z0-9-]{6,20}$/.test(request.member_identifier)
  ) {
    errors.push('member_identifier must contain 6 to 20 letters, numbers, or hyphens.');
  }

  if (!request.consent_data_processing) {
    errors.push('consent_data_processing must be true.');
  }

  if (!request.consent_contact) {
    errors.push('consent_contact must be true.');
  }

  const allowedStatuses: CareRequest['status'][] = [
    'Submitted',
    'Under Review',
    'Approved',
    'Rejected'
  ];

  if (!allowedStatuses.includes(request.status)) {
    errors.push('status must be Submitted, Under Review, Approved, or Rejected.');
  }

  return createValidationResult(errors);
}

export function validateAppointment(
  appointment: Appointment,
  clinics: Clinic[],
  careRequests: CareRequest[]
): ValidationResult {
  const errors: string[] = [];

  if (!appointment.id.trim()) {
    errors.push('Appointment id is required.');
  }

  if (!appointment.care_request_id.trim()) {
    errors.push('care_request_id is required.');
  }

  if (!appointment.clinic_id.trim()) {
    errors.push('clinic_id is required.');
  }

  if (!appointment.preferred_date) {
    errors.push('preferred_date is required.');
  } else if (!isTodayOrFutureDate(appointment.preferred_date)) {
    errors.push('preferred_date must be today or a future date.');
  }

  if (!appointment.preferred_time_window) {
    errors.push('preferred_time_window is required.');
  } else if (!TIME_WINDOWS.includes(appointment.preferred_time_window)) {
    errors.push('preferred_time_window must be a supported appointment window.');
  }

  if (!appointment.service_line) {
    errors.push('service_line is required.');
  } else if (!SERVICE_LINES.includes(appointment.service_line)) {
    errors.push('service_line must be a supported HealthCore service line.');
  }

  const allowedStatuses: Appointment['status'][] = [
    'Pending Review',
    'Scheduled',
    'Completed',
    'Cancelled',
    'No Show'
  ];

  if (!allowedStatuses.includes(appointment.status)) {
    errors.push('status must be Pending Review, Scheduled, Completed, Cancelled, or No Show.');
  }

  const linkedRequest = findById(careRequests, appointment.care_request_id);
  if (!linkedRequest) {
    errors.push('care_request_id must reference an existing care request.');
  } else if (linkedRequest.service_line !== appointment.service_line) {
    errors.push('service_line must match the linked care request.');
  }

  const linkedClinic = findById(clinics, appointment.clinic_id);
  if (!linkedClinic) {
    errors.push('clinic_id must reference an existing clinic.');
  } else if (linkedRequest && linkedClinic.name !== linkedRequest.clinic_location) {
    errors.push('Clinic name must match the linked care request clinic_location.');
  }

  return createValidationResult(errors);
}

export function validateCareRequestCollection(requests: CareRequest[]): ValidationResult {
  if (requests.length === 0) {
    return createValidationResult([]);
  }

  const errors = requests.flatMap((request, index) =>
    validateCareRequest(request).errors.map((message) => `Care request ${index + 1}: ${message}`)
  );

  return createValidationResult(errors);
}
