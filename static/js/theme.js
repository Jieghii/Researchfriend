function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("yantou-theme", theme);
}
function toggleTheme() {
  var cur = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  setTheme(cur);
  var label = document.querySelectorAll("[data-theme-label]");
  label.forEach(function (el) { el.textContent = cur === "light" ? "浅色" : "深色"; });
}
document.addEventListener("click", function (e) {
  if (e.target.closest("[data-theme-toggle]")) toggleTheme();
});
