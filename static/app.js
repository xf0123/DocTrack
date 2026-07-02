document.addEventListener("DOMContentLoaded", () => {
// Upgrade all datetime inputs to force 24-hour format
  flatpickr("input[type='datetime-local']", {
      enableTime: true,
      dateFormat: "Y-m-d\\TH:i",
      time_24hr: true
  });  
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
// --- Kanban Logic ---
document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".kanban-card");
  const columns = document.querySelectorAll(".kanban-column");

  cards.forEach(card => {
    card.addEventListener("dragstart", () => {
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
    });
  });

  columns.forEach(column => {
    column.addEventListener("dragover", e => {
      e.preventDefault();
      const afterElement = getDragAfterElement(column, e.clientY);
      const draggable = document.querySelector(".dragging");
      if (afterElement == null) {
        column.appendChild(draggable);
      } else {
        column.insertBefore(draggable, afterElement);
      }
    });

    column.addEventListener("drop", e => {
      const draggable = document.querySelector(".dragging");
      const taskId = draggable.dataset.id;
      const newBasket = column.id;
      
      // Post change to backend without reloading
      const formData = new FormData();
      formData.append("action", "move");
      formData.append("task_id", taskId);
      formData.append("basket", newBasket);
      
      fetch("/projects", { method: "POST", body: formData });
    });
  });

  function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll(".kanban-card:not(.dragging)")];
    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  // --- Background Reminder Poller ---
  setInterval(checkReminders, 60000); // Check every minute
  function checkReminders() {
    fetch('/projects/reminders')
      .then(r => r.json())
      .then(data => {
        data.reminders.forEach(rem => triggerReminderToast(rem));
      });
  }

  function triggerReminderToast(rem) {
    const container = document.getElementById("toastContainer");
    const toastHtml = `
      <div class="toast show text-bg-warning" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="toast-header text-dark">
          <strong class="me-auto">Task Reminder</strong>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body text-dark">
          ${rem.task}
          <div class="mt-2">
            <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 1)">1 Day</button>
            <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 3)">3 Days</button>
            <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 7)">1 Week</button>
          </div>
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', toastHtml);
  }
});

function snooze(taskId, days) {
  const newDate = new Date();
  newDate.setDate(newDate.getDate() + days);
  
  const formData = new FormData();
  formData.append("action", "snooze");
  formData.append("task_id", taskId);
  formData.append("new_time", newDate.toISOString().slice(0, 16));
  
  fetch("/projects", { method: "POST", body: formData }).then(() => {
    // Reload page to reflect color changes
    window.location.reload(); 
  });
}

// Add to your existing app.js
document.addEventListener("DOMContentLoaded", () => {
    
    // --- Fix Tab Persistence on Reload (Attendance) ---
    if(window.location.hash) {
        const hash = window.location.hash;
        const triggerEl = document.querySelector(`button[data-bs-target="${hash}"]`);
        if (triggerEl) {
            new bootstrap.Tab(triggerEl).show();
        }
    }

    // --- Fix Snooze isolated trigger ---
    window.snooze = function(taskId, days) {
        const newDate = new Date();
        newDate.setDate(newDate.getDate() + days);
        
        const formData = new FormData();
        formData.append("action", "snooze");
        formData.append("task_id", taskId);
        formData.append("new_time", newDate.toISOString().slice(0, 16));
        
        fetch("/projects", { method: "POST", body: formData }).then(() => {
            // Dismiss specific toast
            const toastEl = document.getElementById(`toast-${taskId}`);
            if (toastEl) {
                const toast = bootstrap.Toast.getInstance(toastEl) || new bootstrap.Toast(toastEl);
                toast.hide();
            }
            window.location.reload(); 
        });
    }

    // --- Updated Reminder Check (Isolating Toasts) ---
    function triggerReminderToast(rem) {
        if(document.getElementById(`toast-${rem.id}`)) return; // Prevent duplicates

        const container = document.getElementById("toastContainer");
        const toastHtml = `
          <div id="toast-${rem.id}" class="toast show text-bg-warning mb-2" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="false">
            <div class="toast-header text-dark">
              <strong class="me-auto">Reminder: ${rem.task}</strong>
              <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body text-dark">
              <div class="mt-2 d-flex gap-1 flex-wrap">
                <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 1)">1 Day</button>
                <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 3)">3 Days</button>
                <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 7)">1 Wk</button>
                <button class="btn btn-sm btn-light" onclick="snooze(${rem.id}, 14)">2 Wk</button>
              </div>
            </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', toastHtml);
    }
});

// --- Custom Additions for Trackers ---
document.addEventListener("DOMContentLoaded", () => {
  // 1. Kanban Drag and Drop Logic
  const cards = document.querySelectorAll(".kanban-card");
  const columns = document.querySelectorAll(".kanban-column");

  cards.forEach(card => {
    card.addEventListener("dragstart", () => {
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
    });
  });

  columns.forEach(column => {
    column.addEventListener("dragover", e => {
      e.preventDefault();
      const afterElement = getDragAfterElement(column, e.clientY);
      const draggable = document.querySelector(".dragging");
      if (afterElement == null) {
        column.appendChild(draggable);
      } else {
        column.insertBefore(draggable, afterElement);
      }
    });

    column.addEventListener("drop", e => {
      const draggable = document.querySelector(".dragging");
      const taskId = draggable.dataset.id;
      const newBasket = column.id;
      
      const formData = new FormData();
      formData.append("action", "move");
      formData.append("task_id", taskId);
      formData.append("basket", newBasket);
      
      fetch("/projects", { method: "POST", body: formData });
    });
  });

  function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll(".kanban-card:not(.dragging)")];
    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  // 2. Tab Persistence (Attendance)
  if(window.location.hash) {
      const hash = window.location.hash;
      const triggerEl = document.querySelector(`button[data-bs-target="${hash}"]`);
      if (triggerEl) {
          new bootstrap.Tab(triggerEl).show();
      }
  }

  // 3. Isolated Background Reminders
  setInterval(checkReminders, 60000); 
  function checkReminders() {
    fetch('/projects/reminders')
      .then(r => r.json())
      .then(data => {
        data.reminders.forEach(rem => triggerReminderToast(rem));
      });
  }

  function triggerReminderToast(rem) {
    if(document.getElementById(`toast-${rem.id}`)) return; // Prevent infinite duplicates

    const container = document.getElementById("toastContainer");
    const toastHtml = `
      <div id="toast-${rem.id}" class="toast show mb-2" style="background-color: #ffc107;" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="false">
        <div class="toast-header bg-dark text-white border-bottom border-secondary">
          <strong class="me-auto" style="color: white;">Task Reminder: ${rem.task}</strong>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body" style="color: black !important;">
          <div class="mt-2 d-flex gap-1 flex-wrap">
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 1)">1 Hr</button>
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 2)">2 Hr</button>
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 4)">4 Hr</button>
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 24)">1 Day</button>
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 72)">3 Days</button>
            <button class="btn btn-sm btn-light" onclick="snoozeTask(${rem.id}, 168)">1 Wk</button>
          </div>
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', toastHtml);
  }
}); // End of DOMContentLoaded block

// Global Snooze Function
window.snoozeTask = function(taskId, hoursToAdd) {
    // 1. Get exact current time
    const newDate = new Date();
    // 2. Add the selected hours to current time
    newDate.setHours(newDate.getHours() + hoursToAdd);
    
    // 3. Format it correctly to your local time zone (YYYY-MM-DDTHH:MM)
    const tzOffset = newDate.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(newDate - tzOffset)).toISOString().slice(0, 16);
    
    const formData = new FormData();
    formData.append("action", "snooze");
    formData.append("task_id", taskId);
    formData.append("new_time", localISOTime);
    
    fetch("/projects", { method: "POST", body: formData }).then(() => {
        // Remove ONLY this specific popup window. Leave the rest alone.
        const toastEl = document.getElementById(`toast-${taskId}`);
        if (toastEl) {
            toastEl.remove();
        }
        // Notice we REMOVED the automatic page reload here, 
        // so the other notifications won't disappear.
    });
}