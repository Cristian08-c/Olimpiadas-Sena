// EXPLICACIÓN: Se importan los módulos compartidos.
// MALA PRÁCTICA DETECTADA (original): La clase ParticleSystem estaba duplicada en este archivo y en script.js.
// CORRECCIÓN: Se importa desde un único módulo para reutilizar código y facilitar el mantenimiento.
import ParticleSystem from "./modules/particle-system.js";
import ThemeManager from "./modules/theme-manager.js";

/**
 * @function setupCardInteractions
 * @description Añade interactividad a las tarjetas de evaluación.
 */
const setupCardInteractions = () => {
  const cards = document.querySelectorAll(".card");

  cards.forEach((card) => {
    card.addEventListener("click", async (e) => {
      e.preventDefault();
      const evaluation = card.dataset.evaluation;
      const evaluationUrl = card.getAttribute("href");

      if (evaluationUrl) {
        try {
          // Mostrar indicador de carga
          card.classList.add("loading");

          // Cargar la evaluación mediante AJAX
          const response = await fetch(evaluationUrl);
          if (!response.ok) throw new Error("Error al cargar la evaluación");

          const examData = await response.json();

          // Renderizar la evaluación
          renderExam(examData);

          // Actualizar la URL sin recargar
          history.pushState({ examId: examData.id }, "", evaluationUrl);
        } catch (error) {
          console.error("Error:", error);
          alert("Error al cargar la evaluación. Por favor intente nuevamente.");
        } finally {
          card.classList.remove("loading");
        }
      }
    });
  });
};

/**
 * @function main
 * @description Función de inicialización para la página de evaluaciones.
 */
const main = () => {
  // Se inicializa el gestor de tema.
  new ThemeManager();

  // Se inicializa el sistema de partículas con la configuración por defecto.
  new ParticleSystem("particles-canvas");

  // Se configuran las interacciones.
  setupCardInteractions();
};

/**
 * @function renderQuestion
 * @description Renderiza una pregunta según su tipo
 * @param {Object} question - Datos de la pregunta
 * @param {Number} index - Índice de la pregunta
 */
const renderQuestion = (question, index) => {
  const questionArea = document.querySelector(".question-area");
  const questionHeader = document.getElementById("question-header");
  const questionText = document.getElementById("question-text");
  const optionsList = document.getElementById("options-list");
  const imageContainer = document.getElementById("question-image-container");
  const questionImage = document.getElementById("question-image");

  // Actualizar encabezado y número
  document.getElementById("question-number").textContent = `Pregunta ${
    index + 1
  }`;
  questionText.textContent = question.texto;

  // Manejar imagen si existe
  if (question.imagen_url) {
    questionImage.src = question.imagen_url;
    imageContainer.classList.remove("hidden");
  } else {
    imageContainer.classList.add("hidden");
  }

  // Limpiar opciones anteriores
  optionsList.innerHTML = "";

  switch (question.tipo) {
    case "seleccion":
      question.opciones.forEach((opcion, i) => {
        const li = document.createElement("li");
        li.innerHTML = `
          <label for="q${index}o${i}">
            <input type="radio" name="question${index}" id="q${index}o${i}" value="${i}">
            ${opcion}
          </label>
        `;
        optionsList.appendChild(li);
      });
      break;

    case "completar":
      const textInput = document.createElement("div");
      textInput.className = "completion-input";
      textInput.innerHTML = `
        <textarea
          id="q${index}answer"
          name="question${index}"
          placeholder="Escriba su respuesta aquí..."
          rows="4"
        ></textarea>
      `;
      optionsList.appendChild(textInput);
      break;

    case "relacionar":
      const matchContainer = document.createElement("div");
      matchContainer.className = "matching-container";

      // Columna izquierda
      const leftCol = document.createElement("div");
      leftCol.className = "matching-column";
      question.elementos_izq.forEach((elem, i) => {
        const item = document.createElement("div");
        item.className = "matching-item";
        item.setAttribute("draggable", "true");
        item.dataset.index = i;
        item.textContent = elem;
        leftCol.appendChild(item);
      });

      // Columna derecha
      const rightCol = document.createElement("div");
      rightCol.className = "matching-column";
      question.elementos_der.forEach((elem, i) => {
        const item = document.createElement("div");
        item.className = "matching-item matching-target";
        item.dataset.index = i;
        item.textContent = elem;
        rightCol.appendChild(item);
      });

      matchContainer.appendChild(leftCol);
      matchContainer.appendChild(rightCol);
      optionsList.appendChild(matchContainer);

      // Configurar drag and drop
      setupMatchingDragAndDrop(matchContainer);
      break;
  }
};

/**
 * @function setupMatchingDragAndDrop
 * @description Configura el drag and drop para preguntas de relacionar
 */
const setupMatchingDragAndDrop = (container) => {
  const items = container.querySelectorAll('.matching-item[draggable="true"]');
  const targets = container.querySelectorAll(".matching-target");

  items.forEach((item) => {
    item.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", e.target.dataset.index);
      item.classList.add("dragging");
    });

    item.addEventListener("dragend", () => {
      item.classList.remove("dragging");
    });
  });

  targets.forEach((target) => {
    target.addEventListener("dragover", (e) => {
      e.preventDefault();
      target.classList.add("drag-over");
    });

    target.addEventListener("dragleave", () => {
      target.classList.remove("drag-over");
    });

    target.addEventListener("drop", (e) => {
      e.preventDefault();
      target.classList.remove("drag-over");
      const itemIndex = e.dataTransfer.getData("text/plain");
      const item = container.querySelector(`[data-index="${itemIndex}"]`);

      // Guardar la relación
      saveAnswer({
        leftIndex: parseInt(itemIndex),
        rightIndex: parseInt(target.dataset.index),
      });
    });
  });
};

/**
 * @function renderExam
 * @description Renderiza todo el examen
 */
const renderExam = (examData) => {
  // Ocultar la cuadrícula de tarjetas
  document.querySelector(".card-grid").style.display = "none";

  // Mostrar el área del examen
  document.querySelector(".exam-container").style.display = "block";

  // Renderizar la primera pregunta
  if (examData.preguntas && examData.preguntas.length > 0) {
    renderQuestion(examData.preguntas[0], 0);
  }

  // Inicializar navegación de preguntas
  setupQuestionNavigation(examData.preguntas);
};

document.addEventListener("DOMContentLoaded", main);
