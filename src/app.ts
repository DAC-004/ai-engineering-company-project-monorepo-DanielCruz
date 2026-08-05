import {
  sampleAppointments,
  sampleCareRequests,
  sampleClinics
} from './data/sample.js';
import { filterByCriteria, sortByField } from './utils/collections.js';
import { binarySearchIndexByKey, linearSearchIndex } from './utils/search.js';
import { generateOperationalReports } from './utils/transformations.js';
import {
  validateAppointment,
  validateCareRequest,
  validateCareRequestCollection
} from './utils/validations.js';
import { getCareRequestSummary } from './types/models.js';

const careRequests = sampleCareRequests;
const clinics = sampleClinics;
const appointments = sampleAppointments;

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function setOutput(content: string): void {
  const output = document.getElementById('output');
  if (output) {
    output.textContent = content;
  }
}

function getFilterCriteria(): Record<string, string> {
  const marketCountry = (document.getElementById('filter-country') as HTMLSelectElement | null)?.value ?? '';
  const clinicLocation = (document.getElementById('filter-clinic') as HTMLSelectElement | null)?.value ?? '';
  const serviceLine = (document.getElementById('filter-service') as HTMLSelectElement | null)?.value ?? '';
  const status = (document.getElementById('filter-status') as HTMLSelectElement | null)?.value ?? '';

  const criteria: Record<string, string> = {};
  if (marketCountry) criteria.market_country = marketCountry;
  if (clinicLocation) criteria.clinic_location = clinicLocation;
  if (serviceLine) criteria.service_line = serviceLine;
  if (status) criteria.status = status;
  return criteria;
}

function handleFilter(): void {
  const filtered = filterByCriteria(careRequests, getFilterCriteria());
  setOutput(formatJson(filtered.map(getCareRequestSummary)));
}

function handleSort(): void {
  const direction = (document.getElementById('sort-direction') as HTMLSelectElement | null)?.value as
    | 'asc'
    | 'desc';
  const sorted = sortByField(careRequests, 'preferred_date', direction ?? 'asc');
  setOutput(formatJson(sorted.map(getCareRequestSummary)));
}

function handleLinearSearch(): void {
  const query = (document.getElementById('search-query') as HTMLInputElement | null)?.value.trim() ?? '';
  const index = linearSearchIndex(careRequests, (request) => request.full_name === query);
  if (index === -1) {
    setOutput(`Linear search: no care request found for "${query}".`);
    return;
  }

  setOutput(
    formatJson({
      index,
      result: getCareRequestSummary(careRequests[index])
    })
  );
}

function handleBinarySearch(): void {
  const query = (document.getElementById('search-id') as HTMLInputElement | null)?.value.trim() ?? '';
  const sorted = sortByField(careRequests, 'id', 'asc');
  const index = binarySearchIndexByKey(sorted, 'id', query);
  if (index === -1) {
    setOutput(`Binary search: no care request found for id "${query}".`);
    return;
  }

  setOutput(
    formatJson({
      index,
      result: getCareRequestSummary(sorted[index])
    })
  );
}

function handleReports(): void {
  const reports = generateOperationalReports(careRequests, appointments, clinics);
  setOutput(formatJson(reports));
}

function handleValidation(): void {
  const collectionResult = validateCareRequestCollection(careRequests);
  const appointmentResults = appointments.map((appointment) => ({
    id: appointment.id,
    result: validateAppointment(appointment, clinics, careRequests)
  }));

  setOutput(
    formatJson({
      careRequests: collectionResult,
      sampleSingleRequest: validateCareRequest(careRequests[0]),
      appointments: appointmentResults
    })
  );
}

function bindAction(buttonId: string, handler: () => void): void {
  const button = document.getElementById(buttonId);
  if (button) {
    button.addEventListener('click', handler);
  }
}

bindAction('btn-filter', handleFilter);
bindAction('btn-sort', handleSort);
bindAction('btn-linear-search', handleLinearSearch);
bindAction('btn-binary-search', handleBinarySearch);
bindAction('btn-reports', handleReports);
bindAction('btn-validate', handleValidation);

setOutput('Use the controls above to test HealthCore Milestone 2 data utilities.');
