/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from "@web/core/network/rpc";

/* ========= Guard para evitar SecurityError por mensajes cross-origin ========= */
(function installCrossOriginMessageGuard() {
    if (window.__gameIframeMessageGuardInstalled) return;
    window.__gameIframeMessageGuardInstalled = true;
    window.__gameIframeWindows = window.__gameIframeWindows || new Set();

    window.addEventListener('message', function (event) {
        try {
            if (window.__gameIframeWindows.has(event.source)) {
                event.stopImmediatePropagation();
            }
        } catch (e) { /* ignore */ }
    }, true);
})();

/* ========= Estilos del overlay (inyectados una sola vez) ========= */
(function ensureOverlayStyles() {
    if (document.getElementById('game-overlay-styles')) return;
    const css = `
    .game-overlay-backdrop {
        position: fixed; inset: 0; background: rgba(0,0,0,.6);
        display: flex; align-items: center; justify-content: center;
        z-index: 1050; opacity: 0; transition: opacity .15s ease;
    }
    .game-overlay-backdrop.show { opacity: 1; }
    .game-overlay-container {
    position: relative;
    width: 100vw;
    height: 100vh;
    max-width: none;
    background: #111;
    border-radius: 0;
    overflow: hidden;
    box-shadow: none;
    transform: translateY(0);
    transition: none;
}

    .game-overlay-backdrop.show .game-overlay-container { transform: translateY(0); }
    .game-overlay-header {
        position: absolute; top: 8px; left: 8px; right: 8px; z-index: 2;
        display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }
    .game-toolbar { display: flex; flex-wrap: wrap; gap: 6px; }
    .game-btn {
        border: 0; padding: 6px 10px; border-radius: 8px; color: #fff; cursor: pointer;
        background: rgba(255,255,255,.15);
    }
    .game-btn:hover { background: rgba(255,255,255,.25); }
    .game-overlay-close {
        border: 0; background: rgba(255,255,255,.15); color: #fff;
        padding: 6px 10px; border-radius: 8px;
    }
    .game-overlay-iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; background: #000; }
    .game-badge { color: #fff; font-size: 13px; margin-left: 8px; opacity: .9; min-width: 120px; }
    @media (max-width: 768px){
        .game-overlay-container { width: 100vw; height: 85vh; border-radius: 8px; }
    }
    `;
    const style = document.createElement('style');
    style.id = 'game-overlay-styles';
    style.textContent = css;
    document.head.appendChild(style);
})();

publicWidget.registry.ProductIframe = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    events: {
        'click .show-iframe': '_onShowIframe',            // con registro (Login)
        'click .show-iframe-direct': '_onShowIframeDirect',// directo (sin login)
    },

    /* ===================== Handlers ===================== */
    _onShowIframe(ev) {
        ev.preventDefault(); ev.stopPropagation();
        const $btn = $(ev.currentTarget);
        const productId = $btn.data('product-id');
        const iframeUrl = $btn.data('product-url');
        if (!iframeUrl) return alert('Este juego no tiene una URL configurada.');

        $btn.text('🔄 Iniciando...').prop('disabled', true);

        // Login (usa tu EP alias de start_game)
        rpc('/casino/api/login', { product_id: productId })
            .then((res) => {
                if (res?.error) return alert(res.error);
                this._openOverlay(res.iframe_url || iframeUrl, {
                    productId,
                    sessionId: res.session_id,
                    tracked: true,
                    balance: res.balance || 0,
                });
            })
            .catch(() => alert('Error al conectar con el servidor'))
            .finally(() => $btn.text('🎯 Jugar (Con Registro)').prop('disabled', false));
    },

    _onShowIframeDirect(ev) {
        ev.preventDefault(); ev.stopPropagation();
        const $btn = $(ev.currentTarget);
        const productId = $btn.data('product-id');
        const iframeUrl = $btn.data('product-url');
        if (!iframeUrl) return alert('Este juego no tiene una URL configurada.');

        // Abre overlay sin sesión; podrás hacer Login desde la botonera
        this._openOverlay(iframeUrl, { productId, tracked: false });
    },

    /* ===================== Overlay con toolbar ===================== */
    _openOverlay(iframeUrl, { productId = null, sessionId = null, tracked = false, balance = 0 } = {}) {
        const backdrop = document.createElement('div');
        backdrop.className = 'game-overlay-backdrop';
        const container = document.createElement('div');
        container.className = 'game-overlay-container';
        const header = document.createElement('div');
        header.className = 'game-overlay-header';

        // Toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'game-toolbar';

        // Botones EP
        const btnLogin  = this._makeBtn('🔐 Login', async () => {
            if (!productId) return alert('Producto no identificado.');
            try {
                const res = await rpc('/casino/api/login', { product_id: productId });
                if (res.error) return alert(res.error);
                ov.sessionId = res.session_id;
                ov.tracked = true;
                this._updateBadge(res.balance ?? 0);
                alert('Login OK');
            } catch { alert('Error de red'); }
        });
         // botones de acciones- modificar desde aca
        const btnWin    = this._makeBtn('✅ Ganada', () => this._promptAndCall(sessionIdGetter(), '/casino/api/win'));
        const btnLose   = this._makeBtn('❌ Perdida', () => this._promptAndCall(sessionIdGetter(), '/casino/api/lose'));
        const btnRefund = this._makeBtn('↩️ Devolución', () => this._promptAndCall(sessionIdGetter(), '/casino/api/refund'));
        const btnBalance= this._makeBtn('💰 Balance', () => this._getBalance(sessionIdGetter()));
        const btnEnd    = this._makeBtn('🛑 Terminar', () => this._endSession(sessionIdGetter()));

        toolbar.append(btnLogin, btnWin, btnLose, btnRefund, btnBalance, btnEnd);

        // Badge de saldo
        const badge = document.createElement('span');
        badge.className = 'game-badge';
        badge.textContent = tracked ? `Saldo: ${(+balance).toFixed(2)}` : 'Sin sesión';

        // Cerrar
        const btnClose = document.createElement('button');
        btnClose.className = 'game-overlay-close';
        btnClose.textContent = 'Cerrar';

        header.append(toolbar, badge, btnClose);

        // Iframe
        const iframe = document.createElement('iframe');
        iframe.className = 'game-overlay-iframe';
        iframe.src = iframeUrl;
        iframe.allowFullscreen = true;

        container.append(header, iframe);
        backdrop.appendChild(container);
        document.body.appendChild(backdrop);

        // Estado del overlay
        const ov = this._currentOverlay = {
            backdrop, container, header, toolbar, iframe, badge, btnClose,
            productId, sessionId, tracked
        };

        // Registrar window en guard
        iframe.addEventListener('load', () => {
            try { window.__gameIframeWindows.add(iframe.contentWindow); } catch(e) {}
        });

        // Handlers cierre
        const closeHandler = (e) => { e.preventDefault(); this._closeOverlay(); };
        const keyHandler = (e) => { if (e.key === 'Escape') this._closeOverlay(); };
        const backdropHandler = (e) => { if (e.target === backdrop) this._closeOverlay(); };
        btnClose.addEventListener('click', closeHandler);
        document.addEventListener('keydown', keyHandler);
        backdrop.addEventListener('click', backdropHandler);

        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(() => backdrop.classList.add('show'));

        ov._handlers = { closeHandler, keyHandler, backdropHandler, prevOverflow };

        // Utils que necesitan acceso al estado actual
        const sessionIdGetter = () => this._currentOverlay?.sessionId || null;

        this._updateBadge = (val) => {
            if (!this._currentOverlay?.badge) return;
            const s = this._currentOverlay.tracked ? `Saldo: ${(+val).toFixed(2)}` : 'Sin sesión';
            this._currentOverlay.badge.textContent = s;
        };

        this._promptAndCall = async (sid, url) => {
            if (!this._currentOverlay?.tracked || !sid) return alert('No hay sesión activa. Hacé Login.');
            const raw = prompt('Ingrese monto:');
            if (raw === null) return;
            const amount = parseFloat(String(raw).replace(',', '.'));
            if (Number.isNaN(amount) || amount < 0) return alert('Monto inválido');
            try {
                const res = await rpc(url, { session_id: sid, amount });
                if (res.error) return alert(res.error);
                if (res.balance !== undefined) this._updateBadge(res.balance);
            } catch { alert('Error de red'); }
        };

        this._getBalance = async (sid) => {
            if (!this._currentOverlay?.tracked || !sid) return alert('No hay sesión activa. Hacé Login.');
            try {
                const res = await rpc('/casino/api/balance', { session_id: sid });
                if (res.error) return alert(res.error);
                alert(`Balance actual: ${res.balance}`);
                if (res.balance !== undefined) this._updateBadge(res.balance);
            } catch { alert('Error de red'); }
        };

        this._endSession = async (sid) => {
            if (!sid) return this._closeOverlay();
            try {
                const res = await rpc('/casino/api/end', { session_id: sid });
                console.log('Sesión finalizada:', res);
            } catch {}
            this._closeOverlay();
        };

        return backdrop;
    },

    _makeBtn(label, onClick) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'game-btn';
        b.textContent = label;
        b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onClick(); });
        return b;
    },

    _closeOverlay() {
        const ov = this._currentOverlay;
        if (!ov) return;

        // Quitar del guard
        try { if (ov.iframe) window.__gameIframeWindows.delete(ov.iframe.contentWindow); } catch(e) {}

        // Restaurar eventos/scroll
        if (ov._handlers) {
            ov.btnClose.removeEventListener('click', ov._handlers.closeHandler);
            document.removeEventListener('keydown', ov._handlers.keyHandler);
            ov.backdrop.removeEventListener('click', ov._handlers.backdropHandler);
            document.body.style.overflow = ov._handlers.prevOverflow || '';
        }

        // Cerrar visualmente
        ov.backdrop.classList.remove('show');
        setTimeout(() => ov.backdrop.remove(), 150);
        this._currentOverlay = null;
    },
});

export default publicWidget.registry.ProductIframe;
