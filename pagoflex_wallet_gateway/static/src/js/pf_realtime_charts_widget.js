/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { loadJS } from "@web/core/assets";

export class PfRealtimeChartsWidget extends Component {
    static template = "pagoflex_wallet_gateway.PfRealtimeChartsWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            lastUpdate: null,
            error: null,
            loading: true,
            periodicity: 'daily',
            dateBasis: 'business',
            volumenTotal: 0,
            comisionesTotal: 0,
        });
        this.chartInstances = {};
        
        // Refs for canvas
        this.volumenCanvasRef = useRef("volumenCanvas");
        this.comisionesCanvasRef = useRef("comisionesCanvas");
        this.transferenciasCanvasRef = useRef("transferenciasCanvas");

        this.pollingInterval = null;

        onWillStart(async () => {
            await this.loadChartJs();
        });

        onMounted(() => {
            this.fetchData().then(() => {
                const checkAndRender = () => {
                    if (this.volumenCanvasRef.el) {
                        this.renderCharts();
                        this.startPolling();
                    } else if (!this.state.error) {
                        setTimeout(checkAndRender, 50);
                    }
                };
                checkAndRender();
            });
        });

        onWillUnmount(() => {
            this.stopPolling();
            this.destroyCharts();
        });
    }

    async loadChartJs() {
        if (!window.Chart) {
            try {
                await loadJS("/web/static/lib/Chart/Chart.js");
            } catch (e) {
                console.error("Error loading Chart.js:", e);
            }
        }
    }

    get record() {
        return this.props.record;
    }

    async setPeriodicity(period) {
        if (this.state.periodicity === period) return;
        this.state.periodicity = period;
        await this.fetchData();
        if (this.hasRenderedCharts()) {
            this.updateCharts();
        } else {
            this.destroyCharts();
            await this.waitForRender();
            this.renderCharts();
        }
    }

    async setDateBasis(dateBasis) {
        if (this.state.dateBasis === dateBasis) return;
        this.state.dateBasis = dateBasis;
        await this.fetchData();
        if (this.hasRenderedCharts()) {
            this.updateCharts();
        } else {
            this.destroyCharts();
            await this.waitForRender();
            this.renderCharts();
        }
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value);
    }

    formatNumber(value) {
        return new Intl.NumberFormat('es-AR').format(value);
    }

    async fetchData() {
        try {
            const dateFrom = this.record.data.date_from;
            const dateTo = this.record.data.date_to;
            const filterApp = this.record.data.filter_app || false;
            
            let dateFromStr = null;
            let dateToStr = null;
            
            // Format dates to string
            if (dateFrom) {
                dateFromStr = `${dateFrom.year}-${String(dateFrom.month).padStart(2, '0')}-${String(dateFrom.day).padStart(2, '0')}`;
            }
            if (dateTo) {
                dateToStr = `${dateTo.year}-${String(dateTo.month).padStart(2, '0')}-${String(dateTo.day).padStart(2, '0')}`;
            }

            const result = await this.orm.call(
                "pf.gateway.dashboard",
                "get_realtime_charts_data",
                [
                    dateFromStr,
                    dateToStr,
                    this.state.periodicity,
                    filterApp,
                    this.state.dateBasis
                ]
            );
            this.chartData = result;
            
            // Calculate totals
            this.state.volumenTotal = result.volumen_entrante.datasets.reduce((sum, ds) => sum + (ds.total || 0), 0);
            this.state.comisionesTotal = result.comisiones.datasets.reduce((sum, ds) => sum + (ds.total || 0), 0);
            
            // Format last update time
            const d = new Date(result.last_update);
            this.state.lastUpdate = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
            
            this.state.error = null;
            this.state.loading = false;
        } catch (error) {
            this.state.error = "Error al actualizar datos.";
            this.state.loading = false;
            console.error("Error fetching realtime charts:", error);
        }
    }

    startPolling() {
        // Poll every 30 seconds
        this.pollingInterval = setInterval(async () => {
            // Only update if tab is visible to save resources
            if (document.visibilityState === 'visible') {
                await this.fetchData();
                this.updateCharts();
            }
        }, 30000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
    }

    destroyCharts() {
        Object.values(this.chartInstances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.chartInstances = {};
    }

    waitForRender() {
        return new Promise((resolve) => requestAnimationFrame(resolve));
    }

    hasRenderedCharts() {
        const pairs = [
            [this.chartInstances.volumen, this.volumenCanvasRef.el],
            [this.chartInstances.comisiones, this.comisionesCanvasRef.el],
            [this.chartInstances.transferencias, this.transferenciasCanvasRef.el],
        ];
        return pairs.every(([chart, canvas]) => chart && canvas && canvas.isConnected && chart.canvas === canvas);
    }

    renderCharts() {
        if (!this.chartData || !window.Chart) return;

        // Volumen Entrante
        if (this.volumenCanvasRef.el) {
            this.chartInstances.volumen = new window.Chart(this.volumenCanvasRef.el, {
                type: 'line',
                data: this.chartData.volumen_entrante,
                options: this.getLineChartOptions("Volumen Entrante")
            });
        }

        // Comisiones Generadas
        if (this.comisionesCanvasRef.el) {
            this.chartInstances.comisiones = new window.Chart(this.comisionesCanvasRef.el, {
                type: 'line',
                data: this.chartData.comisiones,
                options: this.getLineChartOptions("Comisiones Generadas")
            });
        }

        const centerTextPlugin = {
            id: 'centerText',
            beforeDraw: function(chart) {
                if (chart.config.type !== 'doughnut') return;
                
                const meta = chart.getDatasetMeta(0);
                if (!meta || !meta.data || meta.data.length === 0) return;
                
                const ctx = chart.ctx;
                const x = meta.data[0].x;
                const y = meta.data[0].y;
                const total = chart.config.data.total || 0;
                
                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                
                ctx.font = 'bold 24px sans-serif';
                ctx.fillStyle = '#212529';
                ctx.fillText(new Intl.NumberFormat('es-AR').format(total), x, y - 8);
                
                ctx.font = '14px sans-serif';
                ctx.fillStyle = '#6c757d';
                ctx.fillText('Total', x, y + 16);
                ctx.restore();
            }
        };

        // Transferencias
        if (this.transferenciasCanvasRef.el) {
            this.chartInstances.transferencias = new window.Chart(this.transferenciasCanvasRef.el, {
                type: 'doughnut',
                data: this.chartData.transferencias,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: { position: 'right' }
                    }
                },
                plugins: [centerTextPlugin]
            });
        }
    }

    updateCharts() {
        if (!this.chartData || !window.Chart) return;
        
        const smartUpdate = (chartInstance, newData) => {
            if (!chartInstance) return;
            // The safest way to update Chart.js and maintain animations is to reassign labels and datasets,
            // then call update. Object.assign on datasets can destroy Chart.js internal meta states.
            chartInstance.data.labels = newData.labels;
            chartInstance.data.datasets = newData.datasets;
            chartInstance.update();
        };

        smartUpdate(this.chartInstances.volumen, this.chartData.volumen_entrante);
        smartUpdate(this.chartInstances.comisiones, this.chartData.comisiones);
        if (this.chartInstances.transferencias) {
            this.chartData.transferencias.total = this.chartData.transferencias.total || 0;
            smartUpdate(this.chartInstances.transferencias, this.chartData.transferencias);
        }
    }

    getLineChartOptions(title) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                title: { display: false, text: title }
            },
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: { beginAtZero: true }
            }
        };
    }
}

export const pfRealtimeChartsField = {
    component: PfRealtimeChartsWidget,
    supportedTypes: ["html", "text", "char"],
};

registry.category("fields").add("pf_realtime_charts", pfRealtimeChartsField);
