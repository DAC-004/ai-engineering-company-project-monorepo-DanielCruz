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

  function getValues() {
    return {
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
  }

  const errorClassNames = ['border-red-600', 'ring-2', 'ring-red-600/20'];
  const successClassNames = ['border-emerald-600', 'ring-2', 'ring-emerald-600/20'];

  function setFieldVisualState(field, state) {
    if (!field) {
      return;
    }

    field.classList.remove(...errorClassNames, ...successClassNames);

    if (state === 'error') {
      field.classList.add(...errorClassNames);
    } else if (state === 'success') {
      field.classList.add(...successClassNames);
    }
  }

  function setError(fieldName, message) {
    const field = fields[fieldName];
    const errorElement = document.getElementById(errorIds[fieldName]);

    if (!field || !errorElement) {
      return;
    }

    errorElement.textContent = message;
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', errorIds[fieldName]);
    setFieldVisualState(field, 'error');
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
    setFieldVisualState(field, null);
  }

  function markFieldSuccess(fieldName) {
    const field = fields[fieldName];

    if (!field) {
      return;
    }

    field.removeAttribute('aria-invalid');
    setFieldVisualState(field, 'success');
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

  function validateField(fieldName, values, options) {
    const opts = options || {};
    const data = values || getValues();
    clearError(fieldName);

    function succeed() {
      if (opts.showSuccess) {
        markFieldSuccess(fieldName);
      }
      return true;
    }

    switch (fieldName) {
      case 'full_name':
        if (!data.full_name) {
          setError('full_name', 'Please enter your full name.');
          return false;
        }
        if (!/^[A-Za-z\s'.-]{2,80}$/.test(data.full_name)) {
          setError('full_name', 'Enter your full name using letters and standard punctuation only.');
          return false;
        }
        return succeed();

      case 'date_of_birth':
        if (!data.date_of_birth) {
          setError('date_of_birth', 'Please enter your date of birth.');
          return false;
        }
        if (!isAdult(data.date_of_birth)) {
          setError('date_of_birth', 'You must be at least 18 years old to submit this form.');
          return false;
        }
        return succeed();

      case 'email':
        if (!data.email) {
          setError('email', 'Please enter your email address.');
          return false;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
          setError('email', 'Enter a valid email address so we can contact you.');
          return false;
        }
        return succeed();

      case 'phone':
        if (!data.phone) {
          setError('phone', 'Please enter your phone number.');
          return false;
        }
        if (data.market_country && phonePatterns[data.market_country] && !phonePatterns[data.market_country].test(data.phone)) {
          const phoneMessage = data.market_country === 'US'
            ? 'For United States care requests, enter a phone number using +1 followed by 10 digits.'
            : 'For United Kingdom care requests, enter a phone number using +44 followed by 10 digits.';
          setError('phone', phoneMessage);
          return false;
        }
        return succeed();

      case 'market_country':
        if (!data.market_country) {
          setError('market_country', 'Please choose the country where you want care.');
          return false;
        }
        return succeed();

      case 'clinic_location':
        if (!data.clinic_location) {
          setError('clinic_location', 'Please choose your preferred clinic location.');
          return false;
        }
        if (data.market_country && !countryLocations[data.market_country].includes(data.clinic_location)) {
          setError('clinic_location', 'Choose a clinic location that matches your selected country of care.');
          return false;
        }
        return succeed();

      case 'service_line':
        if (!data.service_line) {
          setError('service_line', 'Please choose the service you need.');
          return false;
        }
        return succeed();

      case 'preferred_date':
        if (!data.preferred_date) {
          setError('preferred_date', 'Please select your preferred appointment date.');
          return false;
        }
        if (!isFutureDate(data.preferred_date)) {
          setError('preferred_date', 'Choose today or a future date for your appointment request.');
          return false;
        }
        return succeed();

      case 'preferred_time_window':
        if (!data.preferred_time_window) {
          setError('preferred_time_window', 'Please choose a preferred appointment window.');
          return false;
        }
        return succeed();

      case 'communication_channel':
        if (!data.communication_channel) {
          setError('communication_channel', 'Please choose how you would like to receive reminders.');
          return false;
        }
        return succeed();

      case 'payment_model':
        if (!data.payment_model) {
          setError('payment_model', 'Please choose your payment model.');
          return false;
        }
        if (data.market_country && !countryPayments[data.market_country].includes(data.payment_model)) {
          setError('payment_model', 'Choose a payment model that matches your selected country of care.');
          return false;
        }
        return succeed();

      case 'member_identifier':
        if (!data.member_identifier) {
          setError('member_identifier', 'Please enter your insurance or NHS member identifier.');
          return false;
        }
        if (data.payment_model === 'NHS Contract (UK)' && !/^\d{10}$/.test(data.member_identifier)) {
          setError('member_identifier', 'For NHS Contract (UK), enter a 10-digit member identifier.');
          return false;
        }
        if (data.payment_model !== 'NHS Contract (UK)' && !/^[A-Za-z0-9-]{6,20}$/.test(data.member_identifier)) {
          setError('member_identifier', 'Enter an insurance member identifier with 6 to 20 letters, numbers, or hyphens.');
          return false;
        }
        return succeed();

      case 'consent_data_processing':
        if (!data.consent_data_processing) {
          setError('consent_data_processing', 'Please confirm that you understand the data processing terms.');
          return false;
        }
        return succeed();

      case 'consent_contact':
        if (!data.consent_contact) {
          setError('consent_contact', 'Please confirm that HealthCore may send appointment reminders.');
          return false;
        }
        return succeed();

      default:
        return succeed();
    }
  }

  function validate() {
    const values = getValues();
    const fieldNames = Object.keys(errorIds);
    const errors = [];

    fieldNames.forEach(function (fieldName) {
      if (!validateField(fieldName, values)) {
        errors.push(fieldName);
      }
    });

    return { valid: errors.length === 0, errors: errors };
  }

  Object.keys(fields).forEach(function (fieldName) {
    const field = fields[fieldName];
    if (!field) {
      return;
    }

    const eventName = field.type === 'checkbox' || field.tagName === 'SELECT' ? 'change' : 'input';

    field.addEventListener('blur', function () {
      validateField(fieldName, undefined, { showSuccess: true });
    });

    field.addEventListener(eventName, function () {
      validateField(fieldName);

      if (fieldName === 'market_country') {
        validateField('phone');
        validateField('clinic_location');
        validateField('payment_model');
      }

      if (fieldName === 'payment_model') {
        validateField('member_identifier');
      }
    });
  });

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
