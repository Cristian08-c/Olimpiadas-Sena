/**
 * Gestor de temas para la aplicación
 * Maneja el cambio entre tema claro y oscuro
 */
export default class ThemeManager {
  constructor() {
    this.currentTheme = localStorage.getItem("theme") || "light";
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);
    this.setupToggleButton();
  }

  applyTheme(theme) {
    document.body.setAttribute("data-theme", theme);
    this.updateThemeIcon(theme);
    this.currentTheme = theme;
    localStorage.setItem("theme", theme);
  }

  toggleTheme() {
    const newTheme = this.currentTheme === "light" ? "dark" : "light";
    this.applyTheme(newTheme);
  }

  updateThemeIcon(theme) {
    const themeToggle = document.querySelector(".theme-toggle");
    if (themeToggle) {
      const icon = themeToggle.querySelector("i");
      if (icon) {
        icon.className = theme === "light" ? "fas fa-moon" : "fas fa-sun";
      }
    }
  }

  setupToggleButton() {
    const themeToggle = document.querySelector(".theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        this.toggleTheme();
      });
    }
  }

  getCurrentTheme() {
    return this.currentTheme;
  }

  // Método estático para crear una instancia
  static create() {
    return new ThemeManager();
  }
}
