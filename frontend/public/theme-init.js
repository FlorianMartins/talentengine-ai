// Applies the stored theme and language before first paint (external file: the CSP forbids inline scripts).
// Light is the default; dark only applies when the user chose it explicitly in Settings or the top bar.
(function () {
  try {
    var t = localStorage.getItem("te.theme");
    document.documentElement.dataset.theme = t === "dark" ? "dark" : "light";
    var l = localStorage.getItem("te.lang");
    if (l === "en" || l === "fr") document.documentElement.lang = l;
  } catch (e) {}
})();
