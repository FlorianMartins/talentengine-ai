// Applies the stored theme and language before first paint (external file: the CSP forbids inline scripts).
  // Apply the stored theme before first paint to avoid a flash.
  try {
    var t = localStorage.getItem("te.theme");
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    var l = localStorage.getItem("te.lang");
    if (l === "en" || l === "fr") document.documentElement.lang = l;
  } catch (e) {}

