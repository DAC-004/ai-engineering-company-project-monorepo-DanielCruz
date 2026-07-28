import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  sampleAppointments,
  sampleCareRequests,
  sampleClinics
} from '../data/sample.js';
import {
  validateAppointment,
  validateCareRequest,
  validateCareRequestCollection,
  validateClinic
} from '../utils/validations.js';
import {
  createValidAppointment,
  createValidCareRequest,
  createValidClinic,
  futureIsoDate
} from './fixtures.js';

describe('validation utilities', () => {
  it('accepts a valid clinic', () => {
    const result = validateClinic(createValidClinic());
    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
  });

  it('rejects a clinic with an invalid location for the selected country', () => {
    const result = validateClinic(
      createValidClinic({ name: 'London', market_country: 'US' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /allowed location/i);
  });

  it('accepts a valid US care request', () => {
    const result = validateCareRequest(createValidCareRequest());
    assert.equal(result.valid, true);
  });

  it('rejects a care request with an invalid US phone number', () => {
    const result = validateCareRequest(
      createValidCareRequest({ phone: '+155512345' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /\+1 followed by 10 digits/i);
  });

  it('rejects a care request with a clinic location that does not match market_country', () => {
    const result = validateCareRequest(
      createValidCareRequest({ clinic_location: 'London' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /clinic_location must match/i);
  });

  it('rejects a care request with a payment model that does not match market_country', () => {
    const result = validateCareRequest(
      createValidCareRequest({ payment_model: 'NHS Contract (UK)' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /payment_model must match/i);
  });

  it('validates NHS member identifiers as exactly 10 digits', () => {
    const valid = validateCareRequest(
      createValidCareRequest({
        market_country: 'UK',
        clinic_location: 'London',
        phone: '+442079460011',
        payment_model: 'NHS Contract (UK)',
        member_identifier: '1234567890'
      })
    );
    const invalid = validateCareRequest(
      createValidCareRequest({
        market_country: 'UK',
        clinic_location: 'London',
        phone: '+442079460011',
        payment_model: 'NHS Contract (UK)',
        member_identifier: '12345'
      })
    );

    assert.equal(valid.valid, true);
    assert.equal(invalid.valid, false);
    assert.match(invalid.errors.join(' '), /exactly 10 digits/i);
  });

  it('rejects patients under 18 years old', () => {
    const result = validateCareRequest(
      createValidCareRequest({ date_of_birth: '2015-01-01' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /at least 18 years old/i);
  });

  it('rejects preferred dates in the past', () => {
    const result = validateCareRequest(
      createValidCareRequest({ preferred_date: '2020-01-01' })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /today or a future date/i);
  });

  it('requires both consent checkboxes to be true', () => {
    const result = validateCareRequest(
      createValidCareRequest({ consent_contact: false })
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /consent_contact must be true/i);
  });

  it('accepts a valid appointment linked to existing records', () => {
    const careRequest = createValidCareRequest({ id: 'cr-linked' });
    const clinic = createValidClinic({ id: 'clinic-linked', name: 'Austin TX' });
    const appointment = createValidAppointment({
      id: 'appt-linked',
      care_request_id: 'cr-linked',
      clinic_id: 'clinic-linked'
    });

    const result = validateAppointment(appointment, [clinic], [careRequest]);
    assert.equal(result.valid, true);
  });

  it('rejects appointments with mismatched clinic and care request location', () => {
    const careRequest = createValidCareRequest({
      id: 'cr-linked',
      clinic_location: 'Austin TX'
    });
    const clinic = createValidClinic({
      id: 'clinic-miami',
      name: 'Miami FL'
    });
    const appointment = createValidAppointment({
      care_request_id: 'cr-linked',
      clinic_id: 'clinic-miami'
    });

    const result = validateAppointment(appointment, [clinic], [careRequest]);
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /Clinic name must match/i);
  });

  it('rejects appointments when the linked care request does not exist', () => {
    const result = validateAppointment(
      createValidAppointment({ care_request_id: 'missing-request' }),
      [createValidClinic()],
      []
    );
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /existing care request/i);
  });

  it('validates an empty care request collection without errors', () => {
    const result = validateCareRequestCollection([]);
    assert.equal(result.valid, true);
  });

  it('validates bundled sample care requests', () => {
    const result = validateCareRequestCollection(sampleCareRequests);
    assert.equal(result.valid, true, result.errors.join('; '));
  });

  it('validates bundled sample appointments against sample data', () => {
    sampleAppointments.forEach((appointment) => {
      const result = validateAppointment(
        appointment,
        sampleClinics,
        sampleCareRequests
      );
      assert.equal(result.valid, true, `${appointment.id}: ${result.errors.join('; ')}`);
    });
  });

  it('rejects appointments with a past preferred date', () => {
    const careRequest = createValidCareRequest({ id: 'cr-linked' });
    const clinic = createValidClinic({ id: 'clinic-linked' });
    const appointment = createValidAppointment({
      care_request_id: 'cr-linked',
      clinic_id: 'clinic-linked',
      preferred_date: '2020-01-01'
    });

    const result = validateAppointment(appointment, [clinic], [careRequest]);
    assert.equal(result.valid, false);
    assert.match(result.errors.join(' '), /today or a future date/i);
  });

  it('accepts future appointment dates created from fixtures', () => {
    const preferredDate = futureIsoDate(14);
    const careRequest = createValidCareRequest({
      id: 'cr-future',
      preferred_date: preferredDate
    });
    const clinic = createValidClinic({ id: 'clinic-future' });
    const appointment = createValidAppointment({
      care_request_id: 'cr-future',
      clinic_id: 'clinic-future',
      preferred_date: preferredDate
    });

    const result = validateAppointment(appointment, [clinic], [careRequest]);
    assert.equal(result.valid, true);
  });
});
