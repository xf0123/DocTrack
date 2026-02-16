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
});
