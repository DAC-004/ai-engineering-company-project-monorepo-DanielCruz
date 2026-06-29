import type { Appointment, CareRequest, Clinic } from '../types/models.js';

export type CountReport = Record<string, number>;

export type DateRangeReport = {
  minimum: string | null;
  maximum: string | null;
};

export type CareRequestOperationalReports = {
  byMarketCountry: CountReport;
  byClinicLocation: CountReport;
  byServiceLine: CountReport;
  byStatus: CountReport;
  preferredDateRange: DateRangeReport;
  averageDaysUntilPreferredDate: number | null;
};

export type AppointmentOperationalReports = {
  byStatus: CountReport;
  byClinicName: CountReport;
};

function incrementCount(report: CountReport, key: string): void {
  report[key] = (report[key] ?? 0) + 1;
}

export function countByField<T>(items: T[], field: keyof T): CountReport {
  if (items.length === 0) {
    return {};
  }

  return items.reduce<CountReport>((report, item) => {
    incrementCount(report, String(item[field]));
    return report;
  }, {});
}

export function sumNumericField<T>(items: T[], field: keyof T): number {
  if (items.length === 0) {
    return 0;
  }

  let total = 0;
  for (const item of items) {
    const value = item[field];
    if (typeof value === 'number') {
      total += value;
    }
  }

  return total;
}

export function averageNumericField<T>(items: T[], field: keyof T): number | null {
  if (items.length === 0) {
    return null;
  }

  let total = 0;
  let count = 0;

  for (const item of items) {
    const value = item[field];
    if (typeof value === 'number') {
      total += value;
      count += 1;
    }
  }

  if (count === 0) {
    return null;
  }

  return total / count;
}

export function findMinimumStringField<T>(items: T[], field: keyof T): string | null {
  if (items.length === 0) {
    return null;
  }

  let minimum: string | null = null;

  for (const item of items) {
    const value = item[field];
    if (typeof value !== 'string') {
      continue;
    }

    if (minimum === null || value < minimum) {
      minimum = value;
    }
  }

  return minimum;
}

export function findMaximumStringField<T>(items: T[], field: keyof T): string | null {
  if (items.length === 0) {
    return null;
  }

  let maximum: string | null = null;

  for (const item of items) {
    const value = item[field];
    if (typeof value !== 'string') {
      continue;
    }

    if (maximum === null || value > maximum) {
      maximum = value;
    }
  }

  return maximum;
}

function daysUntilDate(isoDate: string, referenceDate: Date = new Date()): number | null {
  const target = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(target.getTime())) {
    return null;
  }

  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);
  const differenceMs = target.getTime() - today.getTime();
  return differenceMs / (1000 * 60 * 60 * 24);
}

export function averageDaysUntilPreferredDate(
  requests: CareRequest[],
  referenceDate: Date = new Date()
): number | null {
  if (requests.length === 0) {
    return null;
  }

  const dayCounts = requests
    .map((request) => daysUntilDate(request.preferred_date, referenceDate))
    .filter((value): value is number => value !== null);

  if (dayCounts.length === 0) {
    return null;
  }

  const total = dayCounts.reduce((sum, value) => sum + value, 0);
  const average = total / dayCounts.length;
  return Math.round(average * 10) / 10;
}

export function generateCareRequestReports(
  requests: CareRequest[]
): CareRequestOperationalReports {
  return {
    byMarketCountry: countByField(requests, 'market_country'),
    byClinicLocation: countByField(requests, 'clinic_location'),
    byServiceLine: countByField(requests, 'service_line'),
    byStatus: countByField(requests, 'status'),
    preferredDateRange: {
      minimum: findMinimumStringField(requests, 'preferred_date'),
      maximum: findMaximumStringField(requests, 'preferred_date')
    },
    averageDaysUntilPreferredDate: averageDaysUntilPreferredDate(requests)
  };
}

export function generateAppointmentReports(
  appointments: Appointment[],
  clinics: Clinic[]
): AppointmentOperationalReports {
  const byClinicName: CountReport = {};

  appointments.forEach((appointment) => {
    const clinic = clinics.find((item) => item.id === appointment.clinic_id) ?? null;
    const clinicName = clinic ? clinic.name : 'Unknown clinic';
    incrementCount(byClinicName, clinicName);
  });

  return {
    byStatus: countByField(appointments, 'status'),
    byClinicName
  };
}

export function generateOperationalReports(
  requests: CareRequest[],
  appointments: Appointment[],
  clinics: Clinic[]
): {
  careRequests: CareRequestOperationalReports;
  appointments: AppointmentOperationalReports;
} {
  return {
    careRequests: generateCareRequestReports(requests),
    appointments: generateAppointmentReports(appointments, clinics)
  };
}
