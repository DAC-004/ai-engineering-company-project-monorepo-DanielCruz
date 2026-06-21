import type {
  Appointment,
  CareRequest,
  Clinic,
  MarketCountry
} from '../types/models.js';

export const sampleClinics: Clinic[] = [
  { id: 'clinic-us-austin', name: 'Austin TX', market_country: 'US' },
  { id: 'clinic-us-houston', name: 'Houston TX', market_country: 'US' },
  { id: 'clinic-us-miami', name: 'Miami FL', market_country: 'US' },
  { id: 'clinic-uk-london', name: 'London', market_country: 'UK' },
  { id: 'clinic-uk-manchester', name: 'Manchester', market_country: 'UK' }
];

function futureDate(daysFromToday: number): string {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + daysFromToday);
  return date.toISOString().slice(0, 10);
}

export const sampleCareRequests: CareRequest[] = [
  {
    id: 'cr-001',
    full_name: 'Jordan Lee',
    date_of_birth: '1990-04-12',
    email: 'jordan.lee@example.com',
    phone: '+15125550199',
    market_country: 'US',
    clinic_location: 'Austin TX',
    service_line: 'Primary Care',
    preferred_date: futureDate(5),
    preferred_time_window: 'Morning (08:00-12:00)',
    communication_channel: 'Email',
    payment_model: 'Private Insurance (US)',
    member_identifier: 'US-INS-1001',
    consent_data_processing: true,
    consent_contact: true,
    status: 'Submitted'
  },
  {
    id: 'cr-002',
    full_name: 'Amelia Wright',
    date_of_birth: '1985-11-03',
    email: 'amelia.wright@example.com',
    phone: '+442079460011',
    market_country: 'UK',
    clinic_location: 'London',
    service_line: 'Specialist Consultation',
    preferred_date: futureDate(10),
    preferred_time_window: 'Afternoon (12:00-17:00)',
    communication_channel: 'SMS',
    payment_model: 'NHS Contract (UK)',
    member_identifier: '1234567890',
    consent_data_processing: true,
    consent_contact: true,
    patient_notes: 'Prefer afternoon appointments when possible.',
    status: 'Under Review'
  },
  {
    id: 'cr-003',
    full_name: 'Marcus Chen',
    date_of_birth: '1978-07-21',
    email: 'marcus.chen@example.com',
    phone: '+15125550288',
    market_country: 'US',
    clinic_location: 'Miami FL',
    service_line: 'Chronic Disease Management',
    preferred_date: futureDate(3),
    preferred_time_window: 'Evening (17:00-20:00)',
    communication_channel: 'Phone Call',
    payment_model: 'Medicare (US)',
    member_identifier: 'MC-778812',
    consent_data_processing: true,
    consent_contact: true,
    status: 'Approved'
  },
  {
    id: 'cr-004',
    full_name: 'Priya Nair',
    date_of_birth: '1992-01-30',
    email: 'priya.nair@example.com',
    phone: '+442079460022',
    market_country: 'UK',
    clinic_location: 'Manchester',
    service_line: 'Preventive Health Programme',
    preferred_date: futureDate(14),
    preferred_time_window: 'Morning (08:00-12:00)',
    communication_channel: 'Email',
    payment_model: 'Private Pay (UK)',
    member_identifier: 'UK-PVT-2201',
    consent_data_processing: true,
    consent_contact: true,
    status: 'Submitted'
  },
  {
    id: 'cr-005',
    full_name: 'Tom Callahan',
    date_of_birth: '1980-09-09',
    email: 'tom.callahan@example.com',
    phone: '+15125550377',
    market_country: 'US',
    clinic_location: 'Houston TX',
    service_line: 'Primary Care',
    preferred_date: futureDate(7),
    preferred_time_window: 'Afternoon (12:00-17:00)',
    communication_channel: 'SMS',
    payment_model: 'Medicaid (US)',
    member_identifier: 'MD-445566',
    consent_data_processing: true,
    consent_contact: true,
    status: 'Rejected'
  }
];

export const sampleAppointments: Appointment[] = [
  {
    id: 'appt-001',
    care_request_id: 'cr-001',
    clinic_id: 'clinic-us-austin',
    preferred_date: futureDate(5),
    preferred_time_window: 'Morning (08:00-12:00)',
    service_line: 'Primary Care',
    status: 'Scheduled'
  },
  {
    id: 'appt-002',
    care_request_id: 'cr-002',
    clinic_id: 'clinic-uk-london',
    preferred_date: futureDate(10),
    preferred_time_window: 'Afternoon (12:00-17:00)',
    service_line: 'Specialist Consultation',
    status: 'Pending Review'
  },
  {
    id: 'appt-003',
    care_request_id: 'cr-003',
    clinic_id: 'clinic-us-miami',
    preferred_date: futureDate(3),
    preferred_time_window: 'Evening (17:00-20:00)',
    service_line: 'Chronic Disease Management',
    status: 'Scheduled'
  },
  {
    id: 'appt-004',
    care_request_id: 'cr-004',
    clinic_id: 'clinic-uk-manchester',
    preferred_date: futureDate(14),
    preferred_time_window: 'Morning (08:00-12:00)',
    service_line: 'Preventive Health Programme',
    status: 'No Show'
  },
  {
    id: 'appt-005',
    care_request_id: 'cr-005',
    clinic_id: 'clinic-us-houston',
    preferred_date: futureDate(7),
    preferred_time_window: 'Afternoon (12:00-17:00)',
    service_line: 'Primary Care',
    status: 'Cancelled'
  }
];

export function findClinicById(clinics: Clinic[], clinicId: string): Clinic | null {
  const clinic = clinics.find((item) => item.id === clinicId);
  return clinic ?? null;
}

export function findCareRequestById(
  requests: CareRequest[],
  requestId: string
): CareRequest | null {
  const request = requests.find((item) => item.id === requestId);
  return request ?? null;
}

export function filterCareRequestsByCountry(
  requests: CareRequest[],
  marketCountry: MarketCountry
): CareRequest[] {
  return requests.filter((request) => request.market_country === marketCountry);
}
