(() => {
  const API_BASE = "http://127.0.0.1:8000";

  const VALID_CATEGORIES = [
    "medical_supplies",
    "laboratory_services",
    "pharmaceutical",
    "clinical_software",
    "it_infrastructure",
    "hr_and_payroll_software",
    "cleaning_and_facilities",
    "patient_communication",
    "billing_and_coding_software",
    "training_platforms",
  ];

  const countryFilter = document.getElementById("filter-country");
  const categoryFilter = document.getElementById("filter-category");
  const categorySelect = document.getElementById("categories");
  const rows = document.getElementById("supplier-rows");
  const listStatus = document.getElementById("list-status");
  const registerForm = document.getElementById("register-form");
  const registerStatus = document.getElementById("register-status");
  const countryInput = document.getElementById("country");
  const currencyInput = document.getElementById("currency");

  const formatMoney = (amount, currency) =>
    `${Number(amount).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ${currency}`;

  const setStatus = (element, message, kind = "") => {
    element.textContent = message;
    element.classList.remove("is-error", "is-ok");
    if (kind) element.classList.add(kind);
  };

  const formatApiError = async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          const location = (item.loc || []).join(".");
          return location ? `${location}: ${item.msg}` : item.msg;
        })
        .join("; ");
    }
    return `Request failed (${response.status})`;
  };

  const populateCategoryControls = () => {
    categoryFilter.innerHTML =
      `<option value="">All categories</option>` +
      VALID_CATEGORIES.map(
        (category) => `<option value="${category}">${category}</option>`
      ).join("");

    categorySelect.innerHTML = VALID_CATEGORIES.map(
      (category) => `<option value="${category}">${category}</option>`
    ).join("");
  };

  const syncCurrencyToCountry = () => {
    if (countryInput.value === "USA") currencyInput.value = "USD";
    if (countryInput.value === "UK") currencyInput.value = "GBP";
  };

  const buildQuery = () => {
    const params = new URLSearchParams();
    if (countryFilter.value) params.set("country", countryFilter.value);
    if (categoryFilter.value) params.set("category", categoryFilter.value);
    const query = params.toString();
    return query ? `?${query}` : "";
  };

  const renderSuppliers = (suppliers) => {
    if (!suppliers.length) {
      rows.innerHTML =
        `<tr><td colspan="7">No suppliers match the current filters.</td></tr>`;
      return;
    }

    rows.innerHTML = suppliers
      .map((supplier) => {
        const statusClass =
          supplier.status === "active" ? "is-active" : "is-suspended";
        const badgeClass =
          supplier.status === "active" ? "badge-active" : "badge-suspended";
        const compliance = supplier.compliance_agreement ?? "—";
        const nextStatus =
          supplier.status === "active" ? "suspended" : "active";
        const toggleLabel =
          supplier.status === "active" ? "Suspend" : "Activate";

        return `
          <tr class="${statusClass}" data-id="${supplier.id}">
            <td>${supplier.name}</td>
            <td>${supplier.country}</td>
            <td>${(supplier.categories || []).join(", ")}</td>
            <td class="rate-cell">${formatMoney(
              supplier.monthly_rate,
              supplier.currency
            )}</td>
            <td>${compliance}</td>
            <td><span class="badge ${badgeClass}">${supplier.status}</span></td>
            <td>
              <div class="row-actions">
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  class="rate-input"
                  value="${supplier.monthly_rate}"
                  aria-label="New monthly rate for ${supplier.name}"
                />
                <button type="button" class="update-rate-btn">Update rate</button>
                <button
                  type="button"
                  class="toggle-status-btn"
                  data-next-status="${nextStatus}"
                >
                  ${toggleLabel}
                </button>
              </div>
            </td>
          </tr>
        `;
      })
      .join("");
  };

  const loadSuppliers = async () => {
    setStatus(listStatus, "Loading suppliers…");
    try {
      const response = await fetch(`${API_BASE}/suppliers${buildQuery()}`);
      if (!response.ok) {
        throw new Error(await formatApiError(response));
      }
      const suppliers = await response.json();
      renderSuppliers(suppliers);
      setStatus(
        listStatus,
        `Showing ${suppliers.length} supplier(s).`,
        "is-ok"
      );
    } catch (error) {
      rows.innerHTML = "";
      setStatus(
        listStatus,
        error.message || "Unable to load suppliers.",
        "is-error"
      );
    }
  };

  const updateRate = async (supplierId, monthlyRate) => {
    const response = await fetch(`${API_BASE}/suppliers/${supplierId}/rate`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ monthly_rate: monthlyRate }),
    });
    if (!response.ok) {
      throw new Error(await formatApiError(response));
    }
    return response.json();
  };

  const updateStatus = async (supplierId, statusValue) => {
    const response = await fetch(`${API_BASE}/suppliers/${supplierId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: statusValue }),
    });
    if (!response.ok) {
      throw new Error(await formatApiError(response));
    }
    return response.json();
  };

  rows.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const row = target.closest("tr[data-id]");
    if (!row) return;
    const supplierId = Number(row.dataset.id);

    try {
      if (target.classList.contains("update-rate-btn")) {
        const input = row.querySelector(".rate-input");
        const monthlyRate = Number(input.value);
        if (!(monthlyRate > 0)) {
          setStatus(
            listStatus,
            "Monthly rate must be greater than zero.",
            "is-error"
          );
          return;
        }
        const updated = await updateRate(supplierId, monthlyRate);
        const rateCell = row.querySelector(".rate-cell");
        rateCell.textContent = formatMoney(
          updated.monthly_rate,
          updated.currency
        );
        input.value = updated.monthly_rate;
        setStatus(
          listStatus,
          `Updated rate for ${updated.name}.`,
          "is-ok"
        );
        return;
      }

      if (target.classList.contains("toggle-status-btn")) {
        const nextStatus = target.dataset.nextStatus;
        const updated = await updateStatus(supplierId, nextStatus);
        await loadSuppliers();
        setStatus(
          listStatus,
          `${updated.name} is now ${updated.status}.`,
          "is-ok"
        );
      }
    } catch (error) {
      setStatus(listStatus, error.message || "Update failed.", "is-error");
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = document.getElementById("name").value.trim();
    const country = countryInput.value;
    const currency = currencyInput.value;
    const monthlyRate = Number(document.getElementById("monthly_rate").value);
    const statusValue = document.getElementById("status").value;
    const selectedCategories = Array.from(categorySelect.selectedOptions).map(
      (option) => option.value
    );
    const compliance = document.getElementById("compliance_agreement").value;
    const renewal = document.getElementById("contract_renewal_date").value;
    const contactEmail = document.getElementById("contact_email").value.trim();
    const notes = document.getElementById("notes").value.trim();

    if (!name || !country || !currency || !statusValue) {
      setStatus(
        registerStatus,
        "Name, country, currency, and status are required.",
        "is-error"
      );
      return;
    }
    if (!selectedCategories.length) {
      setStatus(
        registerStatus,
        "Select at least one category.",
        "is-error"
      );
      return;
    }
    if (!(monthlyRate > 0)) {
      setStatus(
        registerStatus,
        "Monthly rate must be greater than zero.",
        "is-error"
      );
      return;
    }
    if (
      (country === "USA" && currency !== "USD") ||
      (country === "UK" && currency !== "GBP")
    ) {
      setStatus(
        registerStatus,
        "USA requires USD and UK requires GBP.",
        "is-error"
      );
      return;
    }

    const body = {
      name,
      country,
      currency,
      monthly_rate: monthlyRate,
      status: statusValue,
      categories: selectedCategories,
      compliance_agreement: compliance || null,
      contract_renewal_date: renewal || null,
      contact_email: contactEmail || null,
      notes: notes || null,
    };

    try {
      const response = await fetch(`${API_BASE}/suppliers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        throw new Error(await formatApiError(response));
      }
      registerForm.reset();
      syncCurrencyToCountry();
      setStatus(registerStatus, "Supplier registered successfully.", "is-ok");
      await loadSuppliers();
    } catch (error) {
      setStatus(
        registerStatus,
        error.message || "Registration failed.",
        "is-error"
      );
    }
  });

  countryFilter.addEventListener("change", loadSuppliers);
  categoryFilter.addEventListener("change", loadSuppliers);
  countryInput.addEventListener("change", syncCurrencyToCountry);

  populateCategoryControls();
  syncCurrencyToCountry();
  loadSuppliers();
})();
