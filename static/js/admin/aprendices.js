// JavaScript para la página de aprendices
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-aprendices');
    const aprendicesGrid = document.getElementById('aprendices-grid');
    const aprendicesCards = document.querySelectorAll('.aprendiz-card');

    // Función de búsqueda por número de identificación y nombre
    function searchAprendices() {
        // Convertir el término de búsqueda a minúsculas para que no sea sensible a mayúsculas/minúsculas
        const searchTerm = searchInput.value.trim().toLowerCase();

        aprendicesCards.forEach(card => {
            const documentoAprendiz = card.getAttribute('data-documento');
            // Obtener el nombre del nuevo atributo y convertirlo a minúsculas
            const nombreAprendiz = card.getAttribute('data-nombre').toLowerCase();

            // Comprobar si el término de búsqueda está en el documento O en el nombre
            if (
                (documentoAprendiz && documentoAprendiz.includes(searchTerm)) ||
                (nombreAprendiz && nombreAprendiz.includes(searchTerm)) ||
                searchTerm === ''
            ) {
                card.style.display = 'block';
                card.style.animation = 'fadeIn 0.3s ease';
            } else {
                card.style.display = 'none';
            }
        });

        // Mostrar mensaje si no hay resultados
        const visibleCards = Array.from(aprendicesCards).filter(card =>
            card.style.display !== 'none'
        );

        let noResultsMsg = document.getElementById('no-results-message');

        if (visibleCards.length === 0 && searchTerm !== '') {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.id = 'no-results-message';
                noResultsMsg.className = 'no-results';
                noResultsMsg.innerHTML = `
                    <p>No se encontraron resultados para "${searchTerm}"</p>
                    <button onclick="clearSearch()" class="btn-secondary">Limpiar búsqueda</button>
                `;
                aprendicesGrid.appendChild(noResultsMsg);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
    }

    // Event listeners para búsqueda en tiempo real
    searchInput.addEventListener('input', searchAprendices);
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchAprendices();
        }
    });

    // Animación de aparición de tarjetas
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 50);
            }
        });
    }, { threshold: 0.1 });

    aprendicesCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'all 0.4s ease';
        observer.observe(card);
    });

    // Efecto hover en tarjetas
    aprendicesCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
});

// Función global para limpiar búsqueda
function clearSearch() {
    const searchInput = document.getElementById('search-aprendices');
    const noResultsMsg = document.getElementById('no-results-message');

    searchInput.value = '';

    document.querySelectorAll('.aprendiz-card').forEach(card => {
        card.style.display = 'block';
    });

    if (noResultsMsg) {
        noResultsMsg.remove();
    }
}


// El resto del código permanece igual...

// Añadir estilos para animaciones
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .no-results {
        grid-column: 1 / -1;
        text-align: center;
        padding: 2rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        border: 2px dashed #dee2e6;
        margin: 1rem 0;
    }
    
    .no-results p {
        margin-bottom: 1rem;
        color: #6c757d;
    }
`;
document.head.appendChild(style);

// ===== FUNCIÓN PARA APLICAR COLORES A BOTONES HABILITAR/DESHABILITAR =====

// JavaScript SÚPER DIRECTO para aplicar colores
function forceButtonColors() {
    console.log('🔥 FORZANDO COLORES DE BOTONES 🔥');
    
    // Selecciona botones HABILITAR por clase específica
    const habilitarBtns = document.querySelectorAll('a.btn-enable-small, .btn-enable-small');
    console.log('Botones HABILITAR encontrados:', habilitarBtns.length);
    habilitarBtns.forEach((btn, index) => {
        console.log(`Aplicando VERDE a botón ${index}:`, btn.textContent);
        btn.style.setProperty('background', '#28a745', 'important');
        btn.style.setProperty('background-color', '#28a745', 'important');
        btn.style.setProperty('background-image', 'none', 'important');
        btn.style.setProperty('color', 'white', 'important');
        btn.style.setProperty('border', '2px solid #28a745', 'important');
        btn.style.setProperty('font-weight', 'bold', 'important');
        btn.classList.add('verde-forzado');
    });
    
    // Selecciona botones DESHABILITAR por clase específica
    const deshabilitarBtns = document.querySelectorAll('a.btn-disable-small, .btn-disable-small');
    console.log('Botones DESHABILITAR encontrados:', deshabilitarBtns.length);
    deshabilitarBtns.forEach((btn, index) => {
        console.log(`Aplicando AMARILLO a botón ${index}:`, btn.textContent);
        btn.style.setProperty('background', '#ffc107', 'important');
        btn.style.setProperty('background-color', '#ffc107', 'important');
        btn.style.setProperty('background-image', 'none', 'important');
        btn.style.setProperty('color', '#212529', 'important');
        btn.style.setProperty('border', '2px solid #ffc107', 'important');
        btn.style.setProperty('font-weight', 'bold', 'important');
        btn.classList.add('amarillo-forzado');
    });
}

// Ejecutar múltiples veces para asegurar la aplicación de colores
forceButtonColors();
setTimeout(forceButtonColors, 50);
setTimeout(forceButtonColors, 200);
setTimeout(forceButtonColors, 500);
setTimeout(forceButtonColors, 1000);

// También cuando se hace clic en cualquier parte
document.addEventListener('click', function() {
    setTimeout(forceButtonColors, 10);
});

// ===== FUNCIÓN SÚPER AGRESIVA PARA FORZAR VERDE =====

// Función SÚPER AGRESIVA para botones verdes
function forceGreenButtonsAggressive() {
    // Buscar TODOS los botones que digan "Habilitar"
    const allButtons = document.querySelectorAll('a, button, [class*="btn"]');
    let found = 0;
    
    allButtons.forEach(btn => {
        if (btn.textContent && btn.textContent.trim() === 'Habilitar') {
            found++;
            console.log(`🟢 FORZANDO VERDE EN BOTÓN ${found}:`, btn);
            
            // MÉTODO 1: setProperty con important
            btn.style.setProperty('background', '#28a745', 'important');
            btn.style.setProperty('background-color', '#28a745', 'important');
            btn.style.setProperty('background-image', 'none', 'important');
            btn.style.setProperty('color', 'white', 'important');
            btn.style.setProperty('border', '2px solid #28a745', 'important');
            btn.style.setProperty('font-weight', 'bold', 'important');
            
            // MÉTODO 2: setAttribute directo (máxima prioridad)
            const greenStyle = 'background: #28a745 !important; background-color: #28a745 !important; background-image: none !important; color: white !important; border: 2px solid #28a745 !important; font-weight: bold !important; text-decoration: none !important;';
            btn.setAttribute('style', greenStyle);
            
            // MÉTODO 3: cssText directo
            btn.style.cssText = greenStyle;
            
            // Agregar clase y atributo identificador
            btn.classList.add('btn-verde-forzado');
            btn.setAttribute('data-forced-green', 'true');
            
            // Remover clases que puedan interferir
            btn.classList.remove('btn-secondary', 'btn-gray', 'btn-light');
        }
    });
    
    console.log(`✅ Botones "Habilitar" encontrados y modificados: ${found}`);
}

// Función adicional para eventos
function addEventForcing() {
    const habilitarButtons = document.querySelectorAll('a');
    habilitarButtons.forEach(btn => {
        if (btn.textContent && btn.textContent.trim() === 'Habilitar') {
            // Eventos para mantener el color verde
            ['mouseover', 'mouseout', 'focus', 'blur', 'click'].forEach(eventType => {
                btn.addEventListener(eventType, function(e) {
                    setTimeout(() => {
                        this.style.setProperty('background-color', '#28a745', 'important');
                        this.style.setProperty('color', 'white', 'important');
                        this.style.setProperty('border', '2px solid #28a745', 'important');
                    }, 1);
                });
            });
        }
    });
}

// Ejecutar INMEDIATAMENTE cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', forceGreenButtonsAggressive);
} else {
    forceGreenButtonsAggressive();
}

// Ejecutar múltiples veces para asegurar
setTimeout(() => { forceGreenButtonsAggressive(); addEventForcing(); }, 100);
setTimeout(() => { forceGreenButtonsAggressive(); addEventForcing(); }, 300);
setTimeout(() => { forceGreenButtonsAggressive(); addEventForcing(); }, 500);
setTimeout(() => { forceGreenButtonsAggressive(); addEventForcing(); }, 1000);
setTimeout(() => { forceGreenButtonsAggressive(); addEventForcing(); }, 2000);

// Observar cambios en el DOM
const observer = new MutationObserver(forceGreenButtonsAggressive);
observer.observe(document.body, { childList: true, subtree: true });
