import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  sampleAppointments,
  sampleCareRequests,
  sampleClinics
} from '../data/sample.js';
import { filterByCriteria, sortByField } from '../utils/collections.js';
import { binarySearchIndexByKey, linearSearchIndex } from '../utils/search.js';
import { generateOperationalReports } from '../utils/transformations.js';
import {
  validateAppointment,
  validateCareRequestCollection
} from '../utils/validations.js';

describe('milestone 2 integration workflow', () => {
  it('runs the core data processing workflow on bundled sample data', () => {
    assert.equal(validateCareRequestCollection(sampleCareRequests).valid, true);

    sampleAppointments.forEach((appointment) => {
      const result = validateAppointment(
        appointment,
        sampleClinics,
        sampleCareRequests
      );
      assert.equal(result.valid, true);
    });

    const filtered = filterByCriteria(sampleCareRequests, { market_country: 'US' });
    assert.ok(filtered.length >= 1);

    const sorted = sortByField(filtered, 'preferred_date', 'asc');
    const searchIndex = linearSearchIndex(sorted, (request) => request.id === sorted[0].id);
    assert.equal(searchIndex, 0);

    const sortedById = sortByField(sampleCareRequests, 'id', 'asc');
    const binaryIndex = binarySearchIndexByKey(sortedById, 'id', 'cr-003');
    assert.ok(binaryIndex >= 0);

    const reports = generateOperationalReports(
      sampleCareRequests,
      sampleAppointments,
      sampleClinics
    );

    assert.ok(Object.keys(reports.careRequests.byMarketCountry).length >= 2);
    assert.ok(Object.keys(reports.careRequests.byClinicLocation).length >= 3);
    assert.ok(Object.keys(reports.careRequests.byServiceLine).length >= 3);
    assert.ok(Object.keys(reports.careRequests.byStatus).length >= 3);
    assert.ok(reports.careRequests.preferredDateRange.minimum);
    assert.ok(reports.careRequests.preferredDateRange.maximum);
    assert.notEqual(reports.careRequests.averageDaysUntilPreferredDate, null);
    assert.ok(Object.keys(reports.appointments.byStatus).length >= 3);
    assert.ok(Object.keys(reports.appointments.byClinicName).length >= 3);
  });
});
