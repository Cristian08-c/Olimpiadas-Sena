// JavaScript para la página de fichas
document.addEventListener('DOMContentLoaded', function() {
    const fichaCards = document.querySelectorAll('.ficha-card');
    
    // Añadir efectos de hover y click a las fichas
    fichaCards.forEach(card => {
        // Efecto de click con animación
        card.addEventListener('click', function(e) {
            // No navegar si se hizo click en un botón o enlace
            if (e.target.classList.contains('btn-view') || e.target.classList.contains('btn-toggle') || e.target.tagName === 'A') {
                return;
            }
            
            // Añadir efecto de click
            card.style.transform = 'scale(0.98)';
            setTimeout(() => {
                card.style.transform = 'translateY(-5px)';
            }, 100);
            
            // Navegar después de la animación
            setTimeout(() => {
                // Solo navegar si la ficha está activa
                if (!card.classList.contains('ficha-disabled')) {
                    const fichaNum = card.getAttribute('data-ficha-num');
                    if (fichaNum) {
                        window.location.href = `/ficha/${fichaNum}`;
                    }
                } else {
                     // Si está desactivada, revertir la animación sin navegar
                     card.style.transform = 'translateY(-5px)';
                }
            }, 150);
        });
        
        // Mostrar información adicional en hover
        card.addEventListener('mouseenter', function() {
            const fichaInfo = card.querySelector('.ficha-info');
            if (fichaInfo) {
                fichaInfo.style.transform = 'translateY(-2px)';
            }
        });
        
        card.addEventListener('mouseleave', function() {
            const fichaInfo = card.querySelector('.ficha-info');
            if (fichaInfo) {
                fichaInfo.style.transform = 'translateY(0)';
            }
        });
    });
    
    // Animación de aparición de las fichas
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 100);
            }
        });
    }, { threshold: 0.1 });
    
    fichaCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'all 0.6s ease';
        observer.observe(card);
    });
    
    // Estadísticas en tiempo real
    // updateStats(); // Comentado si no se usa o da error
    
    // Funcionalidad de búsqueda por número y nombre de ficha
    const searchInput = document.getElementById('search-fichas');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.trim().toLowerCase();
            const fichaCards = document.querySelectorAll('.ficha-card');
            
            fichaCards.forEach(card => {
                const fichaNumber = card.getAttribute('data-ficha-num');
                const fichaNombre = card.getAttribute('data-ficha-nombre'); // MODIFICADO: Obtener el nombre
                
                // Buscar por número de ficha
                const matchesNumber = fichaNumber && fichaNumber.includes(searchTerm);
                // Buscar por nombre de ficha
                const matchesNombre = fichaNombre && fichaNombre.toLowerCase().includes(searchTerm); // MODIFICADO: Buscar por nombre

                // MODIFICADO: Condición de búsqueda actualizada
                if (searchTerm === '' || matchesNumber || matchesNombre) {
                    card.style.display = 'block';
                    card.style.opacity = '1';
                } else {
                    card.style.display = 'none';
                    card.style.opacity = '0';
                }
            });
            
            // Mostrar mensaje si no hay resultados
            // Corregido para contar correctamente las tarjetas visibles
            let visibleCount = 0;
            fichaCards.forEach(card => {
                if (card.style.display !== 'none') {
                    visibleCount++;
                }
            });

            const noResults = document.getElementById('no-results-fichas');
            
            if (visibleCount === 0 && searchTerm !== '') {
                if (!noResults) {
                    const noResultsDiv = document.createElement('div');
                    noResultsDiv.id = 'no-results-fichas';
                    noResultsDiv.className = 'no-data'; // Reutilizar estilo
                    noResultsDiv.style.width = '100%'; // Asegurar que ocupe espacio
                    noResultsDiv.innerHTML = `
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="opacity: 0.7;"><path d="M11 19C15.4183 19 19 15.4183 19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11C3 15.4183 6.58172 19 11 19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        <h3>No se encontraron fichas</h3>
                        <p>No hay fichas que coincidan con "${searchTerm}"</p>
                    `;
                    document.querySelector('.fichas-grid').appendChild(noResultsDiv);
                } else {
                    // Actualizar el texto si ya existe
                    noResults.querySelector('p').textContent = `No hay fichas que coincidan con "${searchTerm}"`;
                }
            } else if (noResults) {
                noResults.remove();
            }
        });
    }
});

// La función updateStats se mantiene, pero asegúrate de que la ruta '/api/stats' exista y funcione.
function updateStats() {
    fetch('/api/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Actualizar contadores si existen elementos para mostrarlos
            const totalFichas = document.querySelector('[data-stat="total-fichas"]');
            const totalAprendices = document.querySelector('[data-stat="total-aprendices"]');
            const fichasActivas = document.querySelector('[data-stat="fichas-activas"]');
            
            if (totalFichas) totalFichas.textContent = data.total_fichas;
            if (totalAprendices) totalAprendices.textContent = data.total_aprendices;
            if (fichasActivas) fichasActivas.textContent = data.fichas_activas;
        })
        .catch(error => {
            console.warn('Error actualizando estadísticas (esto es opcional):', error);
        });
}

// Función para mostrar detalles de ficha en modal (opcional)
function showFichaDetails(fichaNum) {
    fetch(`/api/fichas`)
        .then(response => response.json())
        .then(data => {
            const ficha = data[fichaNum];
            if (ficha) {
                // Aquí podrías mostrar un modal con detalles de la ficha
                console.log('Detalles de ficha:', ficha);
            }
        })
        .catch(error => {
            console.error('Error cargando detalles de ficha:', error);
        });
}
