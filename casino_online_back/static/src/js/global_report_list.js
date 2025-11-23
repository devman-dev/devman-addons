/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    /**
     * Aplica colores dinámicos a las filas basándose en el hash de la categoría
     */
    getRowClass(record) {
        const className = super.getRowClass(record);
        
        // Solo aplicar en el modelo casino.global.report.line
        if (record.resModel === 'casino.global.report.line') {
            const categoria = record.data.categoria;
            if (categoria) {
                // Lista de clases de color disponibles
                const colorClasses = [
                    'table-info',      // Azul claro
                    'table-success',   // Verde claro
                    'table-warning',   // Amarillo claro
                    'table-danger',    // Rojo claro
                    'table-primary',   // Azul
                    'table-secondary', // Gris
                ];
                
                // Generar hash simple del nombre de categoría
                let hash = 0;
                for (let i = 0; i < categoria.length; i++) {
                    hash = categoria.charCodeAt(i) + ((hash << 5) - hash);
                }
                hash = Math.abs(hash);
                
                // Seleccionar color basado en el hash
                const colorClass = colorClasses[hash % colorClasses.length];
                return `${className} ${colorClass}`;
            }
        }
        
        return className;
    }
});
