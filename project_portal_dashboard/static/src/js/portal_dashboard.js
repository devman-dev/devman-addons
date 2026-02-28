/** @odoo-module **/

// JavaScript adicional para animaciones o funcionalidades interactivas
document.addEventListener('DOMContentLoaded', function() {
    // Animar las tarjetas KPI al cargar
    const kpiCards = document.querySelectorAll('.card');
    kpiCards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            setTimeout(() => {
                card.style.transition = 'all 0.5s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, 50);
        }, index * 100);
    });
});
