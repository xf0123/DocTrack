document.addEventListener("DOMContentLoaded", () => {
  const statusForm = document.getElementById("statusForm");
  const modalLabel = document.getElementById("statusModalLabel");
  const statusButtons = document.querySelectorAll(".js-status-btn");
  const linkPathGroup = document.getElementById("linkPathGroup");
  const linkPathInput = document.getElementById("linkPathInput");

  statusButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!statusForm || !modalLabel) return;
      statusForm.action = btn.dataset.actionUrl;
      modalLabel.textContent = `${btn.dataset.label} Document`;

      const needsLinkPath = btn.dataset.actionUrl.includes("/scan");
      if (linkPathGroup && linkPathInput) {
        linkPathGroup.classList.toggle("d-none", !needsLinkPath);
        linkPathInput.required = needsLinkPath;
        linkPathInput.value = "";
      }
    });
  });

  const filterForm = document.getElementById("documentsFilterForm");
  const filterCheckboxes = document.querySelectorAll(".js-filter-checkbox");
  const searchFilter = document.getElementById("searchFilter");
  const clearFiltersBtn = document.getElementById("clearFiltersBtn");

  const applyFilters = () => {
    if (!filterForm) return;
    if (document.activeElement === searchFilter) {
      sessionStorage.setItem("documents.searchFocus", "1");
    }
    const params = new URLSearchParams(new FormData(filterForm));
    window.location.href = `${window.location.pathname}?${params.toString()}`;
  };

  filterCheckboxes.forEach((field) => {
    field.addEventListener("change", applyFilters);
  });

  let searchDebounce;
  if (searchFilter) {
    if (sessionStorage.getItem("documents.searchFocus") === "1") {
      searchFilter.focus();
      searchFilter.selectionStart = searchFilter.selectionEnd = searchFilter.value.length;
      sessionStorage.removeItem("documents.searchFocus");
    }

    searchFilter.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(applyFilters, 250);
    });
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      sessionStorage.removeItem("documents.searchFocus");
      window.location.href = window.location.pathname;
    });
  }

  const paginationForm = document.getElementById("paginationForm");
  const pageInput = document.getElementById("pageInput");
  if (paginationForm && pageInput) {
    const minPage = Number(pageInput.min || 1);
    const maxPage = Number(pageInput.max || minPage);

    const submitPage = () => {
      const requestedPage = Number(pageInput.value || minPage);
      const safePage = Math.min(Math.max(requestedPage, minPage), maxPage);
      pageInput.value = String(safePage);
      paginationForm.requestSubmit();
    };

    pageInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      submitPage();
    });

    pageInput.addEventListener("change", submitPage);

    paginationForm.querySelectorAll("[data-page-target]").forEach((button) => {
      button.addEventListener("click", () => {
        pageInput.value = button.dataset.pageTarget || pageInput.value;
        submitPage();
      });
    });

    let lastWheelNav = 0;
    document.addEventListener(
      "wheel",
      (event) => {
        const openModal = document.querySelector(".modal.show");
        if (openModal) return;

        const target = event.target;
        if (target instanceof HTMLElement && target.closest("input, textarea, select, [contenteditable='true']")) {
          return;
        }

        const now = Date.now();
        if (now - lastWheelNav < 350) return;

        const delta = event.deltaY;
        if (!delta) return;

        const currentPage = Number(pageInput.value || minPage);
        const nextPage = delta > 0 ? Math.min(currentPage + 1, maxPage) : Math.max(currentPage - 1, minPage);
        if (nextPage === currentPage) return;

        lastWheelNav = now;
        event.preventDefault();
        pageInput.value = String(nextPage);
        submitPage();
      },
      { passive: false }
    );
  }

  const documentRows = document.querySelectorAll(".js-document-row");
  const linkPathViewer = document.getElementById("linkPathViewer");
  const copyLinkPathBtn = document.getElementById("copyLinkPathBtn");
  const editDocumentForm = document.getElementById("editDocumentForm");
  const editType = document.getElementById("editType");
  const editProcess = document.getElementById("editProcess");
  const editDocNo = document.getElementById("editDocNo");
  const editTitle = document.getElementById("editTitle");
  const editRemarks = document.getElementById("editRemarks");

  const linkPathModalElement = document.getElementById("linkPathModal");
  const editModalElement = document.getElementById("editDocumentModal");
  const linkPathModal =
    linkPathModalElement && window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(linkPathModalElement) : null;
  const editDocumentModal =
    editModalElement && window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(editModalElement) : null;

  documentRows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("button, a, input, select, textarea, label")) {
        return;
      }

      const isScanned = row.dataset.scanned === "1";
      if (isScanned) {
        if (!linkPathViewer || !linkPathModal) return;
        const path = row.dataset.linkPath || "";
        if (!path) return;

        linkPathViewer.value = path;
        linkPathModal.show();
        return;
      }

      if (!editDocumentForm || !editType || !editProcess || !editDocNo || !editTitle || !editRemarks || !editDocumentModal) {
        return;
      }

      editDocumentForm.action = `/documents/${row.dataset.docId}/update`;
      editType.value = row.dataset.type || "";
      editProcess.value = row.dataset.process || "";
      editDocNo.value = row.dataset.docNo || "";
      editTitle.value = row.dataset.title || "";
      editRemarks.value = row.dataset.remarks || "";
      editDocumentModal.show();
    });
  });

  if (copyLinkPathBtn && linkPathViewer) {
    copyLinkPathBtn.addEventListener("click", async () => {
      const path = linkPathViewer.value.trim();
      if (!path) return;

      await navigator.clipboard.writeText(path);
      const originalText = copyLinkPathBtn.textContent;
      copyLinkPathBtn.textContent = "Copied!";
      copyLinkPathBtn.disabled = true;

      setTimeout(() => {
        copyLinkPathBtn.textContent = originalText;
        copyLinkPathBtn.disabled = false;
      }, 1200);
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
