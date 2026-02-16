document.addEventListener("DOMContentLoaded", () => {
  const statusForm = document.getElementById("statusForm");
  const modalLabel = document.getElementById("statusModalLabel");
  const statusButtons = document.querySelectorAll(".js-status-btn");

  statusButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!statusForm || !modalLabel) return;
      statusForm.action = btn.dataset.actionUrl;
      modalLabel.textContent = `${btn.dataset.label} Document`;
    });
  });

  const filterForm = document.getElementById("documentsFilterForm");
  const statusFilter = document.getElementById("statusFilter");
  const typeFilter = document.getElementById("typeFilter");
  const processFilter = document.getElementById("processFilter");
  const searchFilter = document.getElementById("searchFilter");
  const clearFiltersBtn = document.getElementById("clearFiltersBtn");

  const applyFilters = () => {
    if (!filterForm) return;
    const params = new URLSearchParams(new FormData(filterForm));
    window.location.href = `${window.location.pathname}?${params.toString()}`;
  };

  [statusFilter, typeFilter, processFilter].forEach((field) => {
    if (!field) return;
    field.addEventListener("change", applyFilters);
  });

  let searchDebounce;
  if (searchFilter) {
    searchFilter.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(applyFilters, 500);
    });
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      window.location.href = window.location.pathname;
    });
  }

  const addDocumentForm = document.getElementById("addDocumentForm");
  const singleCheckboxes = document.querySelectorAll(".js-single-checkbox");
  const selectedType = document.getElementById("selectedType");
  const selectedProcess = document.getElementById("selectedProcess");

  singleCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const group = checkbox.dataset.group;
      document.querySelectorAll(`.js-single-checkbox[data-group="${group}"]`).forEach((item) => {
        if (item !== checkbox) item.checked = false;
      });

      if (group === "type" && selectedType) {
        selectedType.value = checkbox.checked ? checkbox.value : "";
      }
      if (group === "process" && selectedProcess) {
        selectedProcess.value = checkbox.checked ? checkbox.value : "";
      }
    });
  });

  if (addDocumentForm) {
    addDocumentForm.addEventListener("submit", (event) => {
      const rawDocNos = addDocumentForm.dataset.docNos || "[]";
      const existingDocNos = JSON.parse(rawDocNos).map((docNo) => docNo.trim().toLowerCase());
      const docNoField = addDocumentForm.querySelector('textarea[name="doc_no"]');
      const currentDocNo = (docNoField?.value || "").trim().toLowerCase();

      if (existingDocNos.includes(currentDocNo)) {
        const shouldContinue = window.confirm(
          "This document number already exists. Do you want to continue adding it?"
        );
        if (!shouldContinue) {
          event.preventDefault();
        }
      }
    });
  }
});
