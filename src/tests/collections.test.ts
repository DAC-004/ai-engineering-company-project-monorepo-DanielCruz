import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import type { CareRequest } from '../types/models.js';
import {
  filterByCriteria,
  groupByField,
  sortByField,
  sortByMultipleFields
} from '../utils/collections.js';
import { createValidCareRequest } from './fixtures.js';

describe('collections utilities', () => {
  const requests: CareRequest[] = [
    createValidCareRequest({
      id: 'cr-a',
      market_country: 'US',
      clinic_location: 'Austin TX',
      service_line: 'Primary Care',
      status: 'Submitted',
      preferred_date: '2026-07-01'
    }),
    createValidCareRequest({
      id: 'cr-b',
      market_country: 'UK',
      clinic_location: 'London',
      service_line: 'Specialist Consultation',
      status: 'Approved',
      preferred_date: '2026-07-10',
      phone: '+442079460011',
      payment_model: 'Private Pay (UK)',
      member_identifier: 'UK-PVT-2201'
    }),
    createValidCareRequest({
      id: 'cr-c',
      market_country: 'US',
      clinic_location: 'Miami FL',
      service_line: 'Primary Care',
      status: 'Submitted',
      preferred_date: '2026-06-20'
    })
  ];

  it('returns an empty array when filtering an empty collection', () => {
    assert.deepEqual(filterByCriteria([], { market_country: 'US' }), []);
  });

  it('returns all items when filter criteria are empty', () => {
    assert.equal(filterByCriteria(requests, {}).length, 3);
  });

  it('filters by one criterion', () => {
    const filtered = filterByCriteria(requests, { market_country: 'US' });
    assert.equal(filtered.length, 2);
    assert.ok(filtered.every((request) => request.market_country === 'US'));
  });

  it('filters by multiple criteria', () => {
    const filtered = filterByCriteria(requests, {
      market_country: 'US',
      service_line: 'Primary Care'
    });
    assert.equal(filtered.length, 2);
  });

  it('returns an empty array when sort input is empty', () => {
    assert.deepEqual(sortByField([], 'preferred_date'), []);
  });

  it('sorts ascending by preferred_date', () => {
    const sorted = sortByField(requests, 'preferred_date', 'asc');
    assert.deepEqual(
      sorted.map((request) => request.id),
      ['cr-c', 'cr-a', 'cr-b']
    );
  });

  it('sorts descending by preferred_date', () => {
    const sorted = sortByField(requests, 'preferred_date', 'desc');
    assert.deepEqual(
      sorted.map((request) => request.id),
      ['cr-b', 'cr-a', 'cr-c']
    );
  });

  it('sorts by multiple fields when primary values tie', () => {
    const sorted = sortByMultipleFields(requests, [
      { field: 'market_country', direction: 'asc' },
      { field: 'preferred_date', direction: 'asc' }
    ]);
    assert.equal(sorted[0].market_country, 'UK');
    assert.equal(sorted[1].market_country, 'US');
  });

  it('returns an empty object when grouping an empty collection', () => {
    assert.deepEqual(groupByField([], 'market_country'), {});
  });

  it('groups items by field value', () => {
    const grouped = groupByField(requests, 'market_country');
    assert.equal(grouped.US.length, 2);
    assert.equal(grouped.UK.length, 1);
  });
});
