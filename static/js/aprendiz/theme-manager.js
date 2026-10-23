/*
EXPLICACIÓN:
Se ha extraído la lógica del cambio de tema a su propio módulo.
MALA PRÁCTICA DETECTADA (original): La clase estaba dentro de evaluaciones.js,
lo que impedía reutilizarla en otras páginas.
CORRECCIÓN: Ahora es una clase ThemeManager que se puede importar donde se necesite
un botón para cambiar entre modo claro y oscuro.
*/
export default class ThemeManager {
  constructor() {
    this.themeToggleButton = document.getElementById('theme-toggle');
    if (!this.themeToggleButton) return;

    this.sunIcon = this.themeToggleButton.querySelector('.sun-icon');
    this.moonIcon = this.themeToggleButton.querySelector('.moon-icon');

    // Detectar preferencia inicial del sistema o guardada en localStorage
    this.isDark = localStorage.getItem('theme') === 'dark' ||
                  (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);

    this.applyTheme();
    this.initToggleListener();
  }

  applyTheme() {
    document.body.setAttribute('data-theme', this.isDark ? 'dark' : 'light');

    if (this.sunIcon && this.moonIcon) {
      this.sunIcon.style.display = this.isDark ? 'none' : 'block';
      this.moonIcon.style.display = this.isDark ? 'block' : 'none';
    }
  }

  toggleTheme() {
    this.isDark = !this.isDark;
    localStorage.setItem('theme', this.isDark ? 'dark' : 'light');
    this.applyTheme();
  }

  initToggleListener() {
    this.themeToggleButton.addEventListener('click', () => this.toggleTheme());
  }
}