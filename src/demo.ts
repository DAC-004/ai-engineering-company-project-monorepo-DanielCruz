import {
  sampleAppointments,
  sampleCareRequests,
  sampleClinics
} from './data/sample.js';
import { filterByCriteria, sortByField } from './utils/collections.js';
import { binarySearchIndexByKey, linearSearchIndex } from './utils/search.js';
import { generateOperationalReports } from './utils/transformations.js';
import { validateCareRequestCollection } from './utils/validations.js';

const usRequests = filterByCriteria(sampleCareRequests, { market_country: 'US' });
const sortedByDate = sortByField(sampleCareRequests, 'preferred_date', 'asc');
const linearIndex = linearSearchIndex(sampleCareRequests, (request) => request.id === 'cr-003');
const sortedById = sortByField(sampleCareRequests, 'id', 'asc');
const binaryIndex = binarySearchIndexByKey(sortedById, 'id', 'cr-003');
const reports = generateOperationalReports(sampleCareRequests, sampleAppointments, sampleClinics);
const validation = validateCareRequestCollection(sampleCareRequests);

console.log('US care requests:', usRequests.length);
console.log('Sorted preferred dates:', sortedByDate.map((request) => request.preferred_date));
console.log('Linear search index for cr-003:', linearIndex);
console.log('Binary search index for cr-003:', binaryIndex);
console.log('Operational reports:', reports);
console.log('Care request validation valid:', validation.valid);
