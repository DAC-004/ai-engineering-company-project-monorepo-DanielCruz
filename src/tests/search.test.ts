import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import type { CareRequest } from '../types/models.js';
import { sortByField } from '../utils/collections.js';
import {
  binarySearchByKey,
  binarySearchIndexByKey,
  linearSearch,
  linearSearchIndex
} from '../utils/search.js';
import { createValidCareRequest } from './fixtures.js';

describe('search utilities', () => {
  const requests = [
    createValidCareRequest({ id: 'cr-001', full_name: 'Jordan Lee' }),
    createValidCareRequest({ id: 'cr-002', full_name: 'Amelia Wright' }),
    createValidCareRequest({ id: 'cr-003', full_name: 'Marcus Chen' })
  ];

  it('returns -1 for linear search on an empty array', () => {
    const emptyRequests: CareRequest[] = [];
    assert.equal(
      linearSearchIndex(emptyRequests, (item) => item.id === 'missing'),
      -1
    );
    assert.equal(linearSearch(emptyRequests, () => true), null);
  });

  it('finds an element with linear search', () => {
    const index = linearSearchIndex(requests, (request) => request.full_name === 'Marcus Chen');
    assert.equal(index, 2);
    assert.equal(linearSearch(requests, (request) => request.id === 'cr-002')?.id, 'cr-002');
  });

  it('returns -1 when linear search does not find a match', () => {
    assert.equal(
      linearSearchIndex(requests, (request) => request.full_name === 'Unknown Patient'),
      -1
    );
  });

  it('returns -1 for binary search on an empty sorted array', () => {
    assert.equal(binarySearchIndexByKey([], 'id', 'cr-001'), -1);
    assert.equal(binarySearchByKey([], 'id', 'cr-001'), null);
  });

  it('finds an element with binary search on a sorted array', () => {
    const sorted = sortByField(requests, 'id', 'asc');
    assert.equal(binarySearchIndexByKey(sorted, 'id', 'cr-002'), 1);
    assert.equal(binarySearchByKey(sorted, 'id', 'cr-003')?.full_name, 'Marcus Chen');
  });

  it('returns -1 when binary search does not find a match', () => {
    const sorted = sortByField(requests, 'id', 'asc');
    assert.equal(binarySearchIndexByKey(sorted, 'id', 'cr-999'), -1);
    assert.equal(binarySearchByKey(sorted, 'id', 'cr-999'), null);
  });
});
