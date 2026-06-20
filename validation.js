(function () {
  'use strict';

  const form = document.getElementById('healthcore-application-form');
  const status = document.getElementById('form-status');

  if (!form || !status) {
    return;
  }

  const fields = {
    full_name: document.getElementById('full_name'),
    date_of_birth: document.getElementById('date_of_birth'),
    email: document.getElementById('email'),
    phone: document.getElementById('phone'),
    market_country: document.getElementById('market_country'),
    clinic_location: document.getElementById('clinic_location'),
    service_line: document.getElementById('service_line'),
    preferred_date: document.getElementById('preferred_date'),
    preferred_time_window: document.getElementById('preferred_time_window'),
    communication_channel: document.getElementById('communication_channel'),
    payment_model: document.getElementById('payment_model'),
    member_identifier: document.getElementById('member_identifier'),
    consent_data_processing: document.getElementById('consent_data_processing'),
    consent_contact: document.getElementById('consent_contact')
  };

  const errorIds = {
    full_name: 'full_name_error',
    date_of_birth: 'date_of_birth_error',
    email: 'email_error',
    phone: 'phone_error',
    market_country: 'market_country_error',
    clinic_location: 'clinic_location_error',
    service_line: 'service_line_error',
    preferred_date: 'preferred_date_error',
    preferred_time_window: 'preferred_time_window_error',
    communication_channel: 'communication_channel_error',
    payment_model: 'payment_model_error',
    member_identifier: 'member_identifier_error',
    consent_data_processing: 'consent_data_processing_error',
    consent_contact: 'consent_contact_error'
  };

  const countryLocations = {
    US: [
      'Austin, Texas',
      'Houston, Texas',
      'Miami, Florida',
      'Orlando, Florida',
      'Atlanta, Georgia'
    ],
    UK: ['London', 'Manchester']
  };

  const countryPayments = {
    US: ['Private Insurance (US)', 'Medicare (US)', 'Medicaid (US)'],
    UK: ['Private Pay (UK)', 'NHS Contract (UK)']
  };

  const phonePatterns = {
    US: /^\+1\d{10}$/,
    UK: /^\+44\d{10}$/
  };

  function setError(fieldName, message) {
    const field = fields[fieldName];
    const errorElement = document.getElementById(errorIds[fieldName]);

    if (!field || !errorElement) {
      return;
    }

    errorElement.textContent = message;
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', errorIds[fieldName]);
  }

  function clearError(fieldName) {
    const field = fields[fieldName];
    const errorElement = document.getElementById(errorIds[fieldName]);

    if (!field || !errorElement) {
      return;
    }

    errorElement.textContent = '';
    field.removeAttribute('aria-invalid');
    field.removeAttribute('aria-describedby');
  }

  function clearAllErrors() {
    Object.keys(errorIds).forEach(clearError);
  }

  function markStatus(kind, message) {
    status.classList.remove('hidden', 'border-red-300', 'bg-red-50', 'text-red-800', 'border-emerald-300', 'bg-emerald-50', 'text-emerald-800');

    if (kind === 'error') {
      status.classList.add('border-red-300', 'bg-red-50', 'text-red-800');
    } else {
      status.classList.add('border-emerald-300', 'bg-emerald-50', 'text-emerald-800');
    }

    status.textContent = message;
  }

  function isAdult(dateString) {
    const dob = new Date(dateString + 'T00:00:00');
    const today = new Date();

    let age = today.getFullYear() - dob.getFullYear();
    const monthDiff = today.getMonth() - dob.getMonth();

    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
      age -= 1;
    }

    return age >= 18;
  }

  function isFutureDate(dateString) {
    const selected = new Date(dateString + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return selected >= today;
  }

  function validate() {
    clearAllErrors();

    const errors = [];
    const values = {
      full_name: fields.full_name.value.trim(),
      date_of_birth: fields.date_of_birth.value,
      email: fields.email.value.trim(),
      phone: fields.phone.value.trim(),
      market_country: fields.market_country.value,
      clinic_location: fields.clinic_location.value,
      service_line: fields.service_line.value,
      preferred_date: fields.preferred_date.value,
      preferred_time_window: fields.preferred_time_window.value,
      communication_channel: fields.communication_channel.value,
      payment_model: fields.payment_model.value,
      member_identifier: fields.member_identifier.value.trim(),
      consent_data_processing: fields.consent_data_processing.checked,
      consent_contact: fields.consent_contact.checked
    };

    if (!values.full_name) {
      errors.push('full_name');
      setError('full_name', 'Please enter your full name.');
    } else if (!/^[A-Za-z\s'.-]{2,80}$/.test(values.full_name)) {
      errors.push('full_name');
      setError('full_name', 'Enter your full name using letters and standard punctuation only.');
    }

    if (!values.date_of_birth) {
      errors.push('date_of_birth');
      setError('date_of_birth', 'Please enter your date of birth.');
    } else if (!isAdult(values.date_of_birth)) {
      errors.push('date_of_birth');
      setError('date_of_birth', 'You must be at least 18 years old to submit this form.');
    }

    if (!values.email) {
      errors.push('email');
      setError('email', 'Please enter your email address.');
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      errors.push('email');
      setError('email', 'Enter a valid email address so we can contact you.');
    }

    if (!values.phone) {
      errors.push('phone');
      setError('phone', 'Please enter your phone number.');
    }

    if (!values.market_country) {
      errors.push('market_country');
      setError('market_country', 'Please choose the country where you want care.');
    }

    if (!values.clinic_location) {
      errors.push('clinic_location');
      setError('clinic_location', 'Please choose your preferred clinic location.');
    }

    if (!values.service_line) {
      errors.push('service_line');
      setError('service_line', 'Please choose the service you need.');
    }

    if (!values.preferred_date) {
      errors.push('preferred_date');
      setError('preferred_date', 'Please select your preferred appointment date.');
    } else if (!isFutureDate(values.preferred_date)) {
      errors.push('preferred_date');
      setError('preferred_date', 'Choose today or a future date for your appointment request.');
    }

    if (!values.preferred_time_window) {
      errors.push('preferred_time_window');
      setError('preferred_time_window', 'Please choose a preferred appointment window.');
    }

    if (!values.communication_channel) {
      errors.push('communication_channel');
      setError('communication_channel', 'Please choose how you would like to receive reminders.');
    }

    if (!values.payment_model) {
      errors.push('payment_model');
      setError('payment_model', 'Please choose your payment model.');
    }

    if (!values.member_identifier) {
      errors.push('member_identifier');
      setError('member_identifier', 'Please enter your insurance or NHS member identifier.');
    }

    if (!values.consent_data_processing) {
      errors.push('consent_data_processing');
      setError('consent_data_processing', 'Please confirm that you understand the data processing terms.');
    }

    if (!values.consent_contact) {
      errors.push('consent_contact');
      setError('consent_contact', 'Please confirm that HealthCore may send appointment reminders.');
    }

    // Domain-specific validations linked to HealthCore US/UK operations.
    if (values.market_country) {
      if (values.phone && phonePatterns[values.market_country] && !phonePatterns[values.market_country].test(values.phone)) {
        errors.push('phone');
        const phoneMessage = values.market_country === 'US'
          ? 'For United States care requests, enter a phone number using +1 followed by 10 digits.'
          : 'For United Kingdom care requests, enter a phone number using +44 followed by 10 digits.';
        setError('phone', phoneMessage);
      }

      if (values.clinic_location && !countryLocations[values.market_country].includes(values.clinic_location)) {
        errors.push('clinic_location');
        setError('clinic_location', 'Choose a clinic location that matches your selected country of care.');
      }

      if (values.payment_model && !countryPayments[values.market_country].includes(values.payment_model)) {
        errors.push('payment_model');
        setError('payment_model', 'Choose a payment model that matches your selected country of care.');
      }
    }

    if (values.payment_model === 'NHS Contract (UK)' && !/^\d{10}$/.test(values.member_identifier)) {
      errors.push('member_identifier');
      setError('member_identifier', 'For NHS Contract (UK), enter a 10-digit member identifier.');
    }

    if (values.payment_model !== 'NHS Contract (UK)' && values.member_identifier && !/^[A-Za-z0-9-]{6,20}$/.test(values.member_identifier)) {
      errors.push('member_identifier');
      setError('member_identifier', 'Enter an insurance member identifier with 6 to 20 letters, numbers, or hyphens.');
    }

    return { valid: errors.length === 0, errors };
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const result = validate();

    if (!result.valid) {
      markStatus('error', 'Please review the highlighted fields and try submitting your care request again.');
      const firstInvalidName = result.errors[0];
      if (firstInvalidName && fields[firstInvalidName]) {
        fields[firstInvalidName].focus();
      }
      return;
    }

    form.reset();
    markStatus('success', 'Your care request has been submitted. A HealthCore team member will review your details and contact you using the information provided.');
  });

  form.addEventListener('reset', function () {
    clearAllErrors();
    status.classList.add('hidden');
    status.textContent = '';
  });
})();
