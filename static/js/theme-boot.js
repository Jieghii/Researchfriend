(function () {
  var key = "yantou-theme";
  var saved = localStorage.getItem(key);
  var theme = saved || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", theme);
})();
