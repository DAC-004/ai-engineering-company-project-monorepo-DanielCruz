export type MarketCountry = 'US' | 'UK';

export type ServiceLine =
  | 'Primary Care'
  | 'Specialist Consultation'
  | 'Chronic Disease Management'
  | 'Preventive Health Programme';

export type PreferredTimeWindow =
  | 'Morning (08:00-12:00)'
  | 'Afternoon (12:00-17:00)'
  | 'Evening (17:00-20:00)';

export type CommunicationChannel = 'SMS' | 'Email' | 'Phone Call';

export type PaymentModelUS =
  | 'Private Insurance (US)'
  | 'Medicare (US)'
  | 'Medicaid (US)';

export type PaymentModelUK = 'Private Pay (UK)' | 'NHS Contract (UK)';

export type PaymentModel = PaymentModelUS | PaymentModelUK;

export type CareRequestStatus = 'Submitted' | 'Under Review' | 'Approved' | 'Rejected';

export type AppointmentStatus =
  | 'Pending Review'
  | 'Scheduled'
  | 'Completed'
  | 'Cancelled'
  | 'No Show';

export interface Clinic {
  id: string;
  name: string;
  market_country: MarketCountry;
}

export interface CareRequest {
  id: string;
  full_name: string;
  date_of_birth: string;
  email: string;
  phone: string;
  market_country: MarketCountry;
  clinic_location: string;
  service_line: ServiceLine;
  preferred_date: string;
  preferred_time_window: PreferredTimeWindow;
  communication_channel: CommunicationChannel;
  payment_model: PaymentModel;
  member_identifier: string;
  consent_data_processing: boolean;
  consent_contact: boolean;
  patient_notes?: string;
  status: CareRequestStatus;
}

export interface Appointment {
  id: string;
  care_request_id: string;
  clinic_id: string;
  preferred_date: string;
  preferred_time_window: PreferredTimeWindow;
  service_line: ServiceLine;
  status: AppointmentStatus;
}

export const CLINIC_LOCATIONS: Record<MarketCountry, readonly string[]> = {
  US: ['Austin TX', 'Houston TX', 'Miami FL', 'Orlando FL', 'Atlanta GA'],
  UK: ['London', 'Manchester']
};

export const PAYMENT_MODELS: Record<MarketCountry, readonly PaymentModel[]> = {
  US: ['Private Insurance (US)', 'Medicare (US)', 'Medicaid (US)'],
  UK: ['Private Pay (UK)', 'NHS Contract (UK)']
};

export const SERVICE_LINES: readonly ServiceLine[] = [
  'Primary Care',
  'Specialist Consultation',
  'Chronic Disease Management',
  'Preventive Health Programme'
];

export const TIME_WINDOWS: readonly PreferredTimeWindow[] = [
  'Morning (08:00-12:00)',
  'Afternoon (12:00-17:00)',
  'Evening (17:00-20:00)'
];

export const COMMUNICATION_CHANNELS: readonly CommunicationChannel[] = [
  'SMS',
  'Email',
  'Phone Call'
];

export function getClinicDisplayLabel(clinic: Clinic): string {
  return `${clinic.name} (${clinic.market_country})`;
}

export function getCareRequestSummary(request: CareRequest): string {
  return `${request.full_name} — ${request.service_line} at ${request.clinic_location}`;
}

export function getAppointmentSummary(
  appointment: Appointment,
  clinicName: string
): string {
  return `${clinicName} on ${appointment.preferred_date} (${appointment.status})`;
}
