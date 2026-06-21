import type { Appointment, CareRequest, Clinic } from '../types/models.js';

export function futureIsoDate(daysFromToday: number, referenceDate: Date = new Date()): string {
  const date = new Date(referenceDate);
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + daysFromToday);
  return date.toISOString().slice(0, 10);
}

export function createValidClinic(overrides: Partial<Clinic> = {}): Clinic {
  return {
    id: 'clinic-us-austin',
    name: 'Austin TX',
    market_country: 'US',
    ...overrides
  };
}

export function createValidCareRequest(overrides: Partial<CareRequest> = {}): CareRequest {
  return {
    id: 'cr-test-001',
    full_name: 'Jordan Lee',
    date_of_birth: '1990-04-12',
    email: 'jordan.lee@example.com',
    phone: '+15125550199',
    market_country: 'US',
    clinic_location: 'Austin TX',
    service_line: 'Primary Care',
    preferred_date: futureIsoDate(7),
    preferred_time_window: 'Morning (08:00-12:00)',
    communication_channel: 'Email',
    payment_model: 'Private Insurance (US)',
    member_identifier: 'US-INS-1001',
    consent_data_processing: true,
    consent_contact: true,
    status: 'Submitted',
    ...overrides
  };
}

export function createValidAppointment(
  overrides: Partial<Appointment> = {},
  referenceDate: Date = new Date()
): Appointment {
  return {
    id: 'appt-test-001',
    care_request_id: 'cr-test-001',
    clinic_id: 'clinic-us-austin',
    preferred_date: futureIsoDate(7, referenceDate),
    preferred_time_window: 'Morning (08:00-12:00)',
    service_line: 'Primary Care',
    status: 'Scheduled',
    ...overrides
  };
}
