import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  sampleAppointments,
  sampleCareRequests,
  sampleClinics
} from '../data/sample.js';
import {
  averageDaysUntilPreferredDate,
  averageNumericField,
  countByField,
  findMaximumStringField,
  findMinimumStringField,
  generateAppointmentReports,
  generateCareRequestReports,
  generateOperationalReports,
  sumNumericField
} from '../utils/transformations.js';
import { createValidCareRequest } from './fixtures.js';

describe('transformation and report utilities', () => {
  it('handles empty collections for count and numeric helpers', () => {
    assert.deepEqual(countByField([], 'market_country'), {});
    assert.equal(sumNumericField([], 'status'), 0);
    assert.equal(averageNumericField([], 'status'), null);
    assert.equal(findMinimumStringField([], 'preferred_date'), null);
    assert.equal(findMaximumStringField([], 'preferred_date'), null);
    assert.equal(averageDaysUntilPreferredDate([]), null);
  });

  it('counts elements by category', () => {
    const report = countByField(sampleCareRequests, 'market_country');
    assert.equal(report.US, 3);
    assert.equal(report.UK, 2);
  });

  it('finds minimum and maximum ISO date strings', () => {
    const requests = [
      createValidCareRequest({ id: 'a', preferred_date: '2026-08-01' }),
      createValidCareRequest({ id: 'b', preferred_date: '2026-06-15' }),
      createValidCareRequest({ id: 'c', preferred_date: '2026-09-30' })
    ];

    assert.equal(findMinimumStringField(requests, 'preferred_date'), '2026-06-15');
    assert.equal(findMaximumStringField(requests, 'preferred_date'), '2026-09-30');
  });

  it('calculates average days until preferred date using a fixed reference date', () => {
    const referenceDate = new Date('2026-06-21T12:00:00');
    const requests = [
      createValidCareRequest({ id: 'a', preferred_date: '2026-06-23' }),
      createValidCareRequest({ id: 'b', preferred_date: '2026-06-27' })
    ];

    assert.equal(averageDaysUntilPreferredDate(requests, referenceDate), 4);
  });

  it('generates all required care request reports', () => {
    const reports = generateCareRequestReports(sampleCareRequests);

    assert.ok(reports.byMarketCountry.US >= 1);
    assert.ok(reports.byClinicLocation['Austin TX'] >= 1);
    assert.ok(reports.byServiceLine['Primary Care'] >= 1);
    assert.ok(reports.byStatus.Submitted >= 1);
    assert.ok(reports.preferredDateRange.minimum);
    assert.ok(reports.preferredDateRange.maximum);
    assert.notEqual(reports.averageDaysUntilPreferredDate, null);
  });

  it('generates all required appointment reports', () => {
    const reports = generateAppointmentReports(sampleAppointments, sampleClinics);

    assert.ok(reports.byStatus.Scheduled >= 1);
    assert.ok(reports.byClinicName['Austin TX'] >= 1);
  });

  it('generates combined operational reports', () => {
    const reports = generateOperationalReports(
      sampleCareRequests,
      sampleAppointments,
      sampleClinics
    );

    assert.ok(reports.careRequests.byMarketCountry);
    assert.ok(reports.appointments.byClinicName);
  });

  it('labels unknown clinics in appointment reports', () => {
    const reports = generateAppointmentReports(
      [
        {
          id: 'appt-unknown',
          care_request_id: 'cr-001',
          clinic_id: 'missing-clinic',
          preferred_date: '2026-07-01',
          preferred_time_window: 'Morning (08:00-12:00)',
          service_line: 'Primary Care',
          status: 'Scheduled'
        }
      ],
      sampleClinics
    );

    assert.equal(reports.byClinicName['Unknown clinic'], 1);
  });
});
