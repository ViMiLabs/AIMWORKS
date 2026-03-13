
document.querySelectorAll("[data-table-filter]").forEach((input) => {
  const table = document.getElementById(input.dataset.tableFilter);
  if (!table) return;
  input.addEventListener("input", () => {
    const needle = input.value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.style.display = row.textContent.toLowerCase().includes(needle) ? "" : "none";
    });
  });
});

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.textContent);
      const label = button.textContent;
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = label; }, 1200);
    } catch (error) {
      button.textContent = "Copy failed";
      setTimeout(() => { button.textContent = "Copy query"; }, 1200);
    }
  });
});
