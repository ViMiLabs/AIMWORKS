
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
