// EXPLICACIÓN: Se importa el módulo del sistema de partículas. Esto evita la duplicación
// de código y mantiene el script de la página enfocado en su propia lógica.
import ParticleSystem from "./modules/particle-system.js";

/**
 * @function setupNumericInput
 * @description Asegura que un campo de entrada solo acepte valores numéricos.
 * MALA PRÁCTICA DETECTADA (original): Lógica de validación inline.
 * CORRECCIÓN: Se abstrae a una función reutilizable.
 * @param {string} inputId - El ID del elemento input.
 */
const setupNumericInput = (inputId) => {
  const input = document.getElementById(inputId);
  if (!input) return;

  const formatInput = (value) => value.replace(/[^0-9]/g, "");

  input.addEventListener("input", (e) => {
    e.target.value = formatInput(e.target.value);
  });
};

/**
 * @function handleFormSubmit
 * @description Gestiona la validación y el envío del formulario de login.
 */
const handleFormSubmit = () => {
  const form = document.getElementById("login-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const documentInput = form.elements.document;
    const passwordInput = form.elements.password;
    const submitButton = form.querySelector('button[type="submit"]');

    // Validaciones del lado del cliente
    let isValid = true;
    if (documentInput.value.trim().length < 6) {
      showMessage("La cédula debe tener al menos 6 dígitos.", "error");
      isValid = false;
    }
    if (!passwordInput.value.trim()) {
      showMessage("Por favor, ingresa tu contraseña.", "error");
      isValid = false;
    }

    if (!isValid) return;

    // Preparar datos para envío
    const formData = new FormData();
    formData.append("document", documentInput.value.trim());
    formData.append("password", passwordInput.value.trim());

    // Cambiar estado del botón
    const originalText = submitButton.textContent;
    submitButton.textContent = "Iniciando sesión...";
    submitButton.disabled = true;

    try {
      // Enviar petición al servidor
      const response = await fetch("/login", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        showMessage(result.message, "success");

        // Pequeña pausa para mostrar el mensaje de éxito
        setTimeout(() => {
          window.location.href = result.redirect;
        }, 1000);
      } else {
        showMessage(result.message, "error");

        // Restaurar botón
        submitButton.textContent = originalText;
        submitButton.disabled = false;

        // Limpiar contraseña por seguridad
        passwordInput.value = "";
      }
    } catch (error) {
      console.error("Error en el login:", error);
      showMessage("Error de conexión. Inténtalo de nuevo.", "error");

      // Restaurar botón
      submitButton.textContent = originalText;
      submitButton.disabled = false;
    }
  });
};

/**
 * @function showMessage
 * @description Muestra mensajes de error o éxito al usuario
 * @param {string} message - El mensaje a mostrar
 * @param {string} type - Tipo de mensaje: 'success' o 'error'
 */
const showMessage = (message, type) => {
  // Remover mensaje anterior si existe
  const existingMessage = document.querySelector(".login-message");
  if (existingMessage) {
    existingMessage.remove();
  }

  // Crear nuevo mensaje
  const messageDiv = document.createElement("div");
  messageDiv.className = `login-message ${type}`;
  messageDiv.textContent = message;

  // Estilos para el mensaje
  messageDiv.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 5px;
    color: white;
    font-weight: bold;
    z-index: 1000;
    max-width: 300px;
    word-wrap: break-word;
    animation: slideIn 0.3s ease-out;
    ${
      type === "success"
        ? "background-color: #28a745;"
        : "background-color: #dc3545;"
    }
  `;

  // Agregar animación CSS
  if (!document.querySelector("#message-animation-styles")) {
    const style = document.createElement("style");
    style.id = "message-animation-styles";
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
      @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(messageDiv);

  // Remover mensaje después de 5 segundos
  setTimeout(() => {
    if (messageDiv.parentNode) {
      messageDiv.style.animation = "slideOut 0.3s ease-in";
      setTimeout(() => {
        messageDiv.remove();
      }, 300);
    }
  }, 5000);
};

/**
 * @function main
 * @description Función principal que se ejecuta al cargar el script.
 * Se utiliza para organizar la inicialización del código.
 */
const main = () => {
  // Se inicializa el sistema de partículas con configuración específica para esta página.
  new ParticleSystem("particles-canvas", {
    particleColor: "rgba(255, 255, 255, 0.5)",
    lineColor: "rgba(255, 255, 255, 0.1)",
  });

  // Se configuran los manejadores de eventos
  setupNumericInput("document");
  handleFormSubmit();
};

// Se asegura que el DOM esté completamente cargado antes de ejecutar el script.
document.addEventListener("DOMContentLoaded", main);
