/** @odoo-module **/

import { Component, mount, onWillStart, onWillUnmount, useState, xml } from "@odoo/owl";

const DEFAULT_REFRESH_MS = 10000;
const FACT_LABEL_FRAGMENT = "factur";

const onReady = (cb) => {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", cb, { once: true });
    console.log("Lanzamiento de WhenReady")
  } else {
    cb();
  }
};

const toInt = (value, fallback) => {
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

class CasinoMovementsResults extends Component {
  static template = xml`
    <div class="o_movements_results_root">
      <t t-if="state.loaded">
        <div class="table-responsive">
          <table class="table table-sm table-hover mb-0 o_transaction_list_table">
            <thead style="font-size:0.9rem;">
              <tr>
                <th>Fecha333</th>
                <th>Descripcion</th>
                <th class="text-end">Monto</th>
                <th class="text-end o-movements-balance-col">Saldo</th>
                <th class="text-center">Detalle</th>
              </tr>
            </thead>
            <tbody style="font-size:0.9rem;">
              <t t-if="state.movements.length === 0">
                <tr>
                  <td class="text-center" colspan="5">Sin movimientos.</td>
                </tr>
              </t>
              <t t-foreach="state.movements" t-as="movement" t-key="movement.id">
                <t t-set="isFact" t-value="isFactMovement(movement)" />
                <t t-set="signedAmount" t-value="getSignedAmount(movement, isFact)" />
                <t t-set="signedBalance" t-value="getSignedBalance(movement, isFact)" />
                <tr>
                  <td>
                    <t t-esc="movement.date" />
                  </td>
                  <td>
                    <t t-esc="movement.description" />
                  </td>
                  <td class="text-end">
                    <span t-if="signedAmount &gt;= 0" class="text-success">
                      +$<t t-esc="formatMoney(signedAmount)" />
                    </span>
                    <span t-else="" class="text-danger">
                      $<t t-esc="formatMoney(signedAmount)" />
                    </span>
                  </td>
                  <td class="text-end o-movements-balance-col">
                    <strong>
                      <span t-if="signedBalance &gt;= 0" class="text-success">
                        $<t t-esc="formatMoney(signedBalance)" />
                      </span>
                      <span t-else="" class="text-danger">
                        -$<t t-esc="formatMoney(Math.abs(signedBalance))" />
                      </span>
                    </strong>
                  </td>
                  <td class="text-center">
                    <t t-if="movement.session">
                      <button type="button"
                        class="btn btn-outline-secondary btn-sm"
                        t-att-data-bs-toggle="'collapse'"
                        t-att-data-bs-target="'#session-details-' + movement.id"
                        t-att-aria-controls="'session-details-' + movement.id"
                        aria-expanded="false"
                        title="Ver detalle">
                        <i class="fa fa-search" />
                      </button>
                    </t>
                    <t t-else="">
                      <span class="text-muted">-</span>
                    </t>
                  </td>
                </tr>
                <tr t-if="movement.session">
                  <td colspan="5" class="p-0">
                    <div class="collapse" t-att-id="'session-details-' + movement.id">
                      <div class="card card-body border-0 border-top">
                        <div class="row g-2">
                          <div class="col-md-6 col-lg-4">
                            <strong>Juego:</strong>
                            <t t-esc="movement.session.game || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Round ID:</strong>
                            <t t-esc="movement.session.round_id || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Transaction ID:</strong>
                            <t t-esc="movement.session.transaction_id || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>End Round:</strong>
                            <t t-esc="movement.session.end_round ? 'true' : 'false'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Amount:</strong>
                            $<t t-esc="formatMoney(movement.session.amount)" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Event ID:</strong>
                            <t t-esc="movement.session.event_id || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Event Date:</strong>
                            <t t-esc="movement.session.event_date || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Description:</strong>
                            <t t-esc="movement.session.market_id || '-'" />
                          </div>
                          <div class="col-md-6 col-lg-4">
                            <strong>Start:</strong>
                            <t t-esc="movement.session.start || '-'" />
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </t>
            </tbody>
          </table>
        </div>

        <div class="d-flex align-items-center justify-content-between p-3 border-top">
          <div class="small text-muted">
            Mostrando <t t-esc="firstItem" />-<t t-esc="lastItem" />
            de <t t-esc="state.total" />
          </div>

          <nav class="align-self-center mt-2" aria-label="Pagination">
            <ul class="pagination mb-0">
              <li class="page-item" t-att-class="state.page &lt;= 1 ? 'disabled' : ''">
                <a class="page-link" t-att-href="buildPageHref(state.page - 1)">«</a>
              </li>
              <t t-foreach="pageRange" t-as="pageNum" t-key="pageNum">
                <li class="page-item" t-att-class="pageNum === state.page ? 'active' : ''">
                  <a class="page-link" t-att-href="buildPageHref(pageNum)">
                    <t t-esc="pageNum" />
                  </a>
                </li>
              </t>
              <li class="page-item" t-att-class="state.page &gt;= state.pageCount ? 'disabled' : ''">
                <a class="page-link" t-att-href="buildPageHref(state.page + 1)">»</a>
              </li>
            </ul>
          </nav>
        </div>
      </t>
      <t t-else="">
        <t t-raw="props.initialHtml" />
      </t>
    </div>
  `;

  setup() {
    this.state = useState({
      loaded: false,
      movements: [],
      total: 0,
      page: 1,
      pageCount: 1,
      pageSize: 10,
      filters: { startDate: "", endDate: "", types: [] },
    });
    this._lastSignature = null;
    this._refreshMs = this.props.refreshInterval || DEFAULT_REFRESH_MS;

    onWillStart(async () => {
      console.log("Lanzamiento de OnWillStart");
      await this._loadData({ force: true });
      this._interval = setInterval(() => this._loadData({ force: false }), this._refreshMs);
    });

    onWillUnmount(() => {
      if (this._interval) {
        clearInterval(this._interval);
        this._interval = null;
      }
    });
  }

  get pageRange() {
    const pages = [];
    for (let i = 1; i <= this.state.pageCount; i += 1) {
      pages.push(i);
    }
    return pages;
  }

  get firstItem() {
    if (!this.state.total) return 0;
    return (this.state.page - 1) * this.state.pageSize + 1;
  }

  get lastItem() {
    if (!this.state.total) return 0;
    return Math.min(this.state.page * this.state.pageSize, this.state.total);
  }

  _readFiltersFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const startDate = params.get("start_date") || "";
    const endDate = params.get("end_date") || "";
    const types = params.getAll("types").filter(Boolean);
    const page = toInt(params.get("page"), 1);
    const pageSize = toInt(params.get("page_size"), 10);

    return { startDate, endDate, types, page, pageSize };
  }

  async _loadData({ force }) {
    console.log("Lanzamiento de LoadData");
    const { startDate, endDate, types, page, pageSize } = this._readFiltersFromUrl();
    const payload = {
      start_date: startDate || false,
      end_date: endDate || false,
      types: types.length ? types : false,
      page,
      page_size: pageSize,
    };

    try {
      const response = await fetch(this.props.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "call",
          params: payload,
        }),
      });

      const result = await response.json();
      const data = result.result || {};

      const firstId = data.movements && data.movements.length ? data.movements[0].id : 0;
      const signature = `${data.total_movements}|${data.page}|${firstId}`;

      if (!force && signature === this._lastSignature) {
        return;
      }

      this._lastSignature = signature;
      this.state.loaded = true;
      this.state.movements = data.movements || [];
      this.state.total = data.total_movements || 0;
      this.state.page = data.page || 1;
      this.state.pageCount = data.page_count || 1;
      this.state.pageSize = data.page_size || pageSize || 10;
      this.state.filters = { startDate, endDate, types };
    } catch (error) {
      console.error("Error loading movements data:", error);
    }
  }

  buildPageHref(pageNum) {
    const params = new URLSearchParams();
    if (this.state.filters.startDate) {
      params.set("start_date", this.state.filters.startDate);
    }
    if (this.state.filters.endDate) {
      params.set("end_date", this.state.filters.endDate);
    }
    if (this.state.filters.types.length) {
      for (const t of this.state.filters.types) {
        params.append("types", t);
      }
    }
    params.set("page_size", this.state.pageSize || 10);
    params.set("page", pageNum);

    return `${window.location.pathname}?${params.toString()}#movimientos_form`;
  }

  isFactMovement(movement) {
    const label = (movement.type_display || "").toLowerCase();
    return label.includes(FACT_LABEL_FRAGMENT);
  }

  getSignedAmount(movement, isFact) {
    const amount = Number(movement.amount || 0);
    return isFact ? -amount : amount;
  }

  getSignedBalance(movement, isFact) {
    const balance = Number(movement.balance || 0);
    return isFact ? -balance : balance;
  }

  formatMoney(amount) {
    const safe = Number.isFinite(amount) ? amount : 0;
    return safe.toFixed(2);
  }
}

// Rastrear contenedores ya montados
const mountedContainers = new Set();

onReady(() => {
  console.log("🔍 [MovementsLive] onReady callback ejecutado");
  initMovements();
});

// También intentar inicializar inmediatamente
function initMovements() {
  console.log("🔍 [MovementsLive] initMovements - Buscando contenedores...");
  const containers = document.querySelectorAll(".o_movements_results_owl");
  console.log(`🔍 [MovementsLive] Encontrados ${containers.length} contenedores`);

  if (containers.length === 0) {
    console.warn("⚠️ [MovementsLive] No se encontraron contenedores. Reintentando en 500ms...");
    setTimeout(initMovements, 500);
    return;
  }

  containers.forEach((el, index) => {
    // Verificar si ya fue montado
    if (mountedContainers.has(el)) {
      console.log(`⏭️ [MovementsLive] Componente ${index + 1} ya está montado, omitiendo...`);
      return;
    }

    console.log(`🚀 [MovementsLive] Montando componente ${index + 1}...`);
    console.log("Contenedor:", el);
    console.log("Contenedor es válido:", el && el.nodeType === 1);
    console.log("Endpoint:", el.dataset.endpoint);
    console.log("RefreshInterval:", el.dataset.refreshInterval);

    const refreshInterval = toInt(el.dataset.refreshInterval, DEFAULT_REFRESH_MS);

    try {
      // Marcar como montado ANTES de intentar montar
      mountedContainers.add(el);

      const component = mount(CasinoMovementsResults, {
        target: el,
        props: {
          endpoint: el.dataset.endpoint || "/my/movimientos/data",
          refreshInterval,
          initialHtml: el.innerHTML,
        },
      });
      console.log(`✅ [MovementsLive] Componente ${index + 1} montado exitosamente`);
    } catch (error) {
      console.error(`❌ [MovementsLive] Error montando componente ${index + 1}:`, error);
      console.error("Message:", error.message);
      console.error("Stack:", error.stack);

      // Remover de montados si falló
      mountedContainers.delete(el);
    }
  });
}

// Log inmediato cuando el módulo se carga
console.log("📦 [MovementsLive] ===== MÓDULO CARGADO =====");

export default CasinoMovementsResults;
