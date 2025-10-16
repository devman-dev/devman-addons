/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from "@web/core/network/rpc";

/* ========= Guard cross-origin ========= */
(function installCrossOriginMessageGuard() {
    if (window.__gameIframeMessageGuardInstalled) return;
    window.__gameIframeMessageGuardInstalled = true;
    window.__gameIframeWindows = window.__gameIframeWindows || new Set();
    window.addEventListener('message', function (event) {
        try { if (window.__gameIframeWindows.has(event.source)) event.stopImmediatePropagation(); } catch (e) { }
    }, true);
})();

/* ========= Estilos del overlay ========= */
(function ensureOverlayStyles() {
    if (document.getElementById('game-overlay-styles')) return;
    const css = `
    .game-overlay-root{
        position:fixed; inset:0;
        background:#000;                /* fullscreen sin backdrop */
        z-index:1050;
        opacity:0; transition:opacity .15s ease;
    }
    .game-overlay-root.show{ opacity:1; }

    .game-overlay-header{
        position:absolute; top:8px; left:8px; right:8px;
        z-index:10;                     /* por encima del iframe */
        display:flex; align-items:center; justify-content:space-between; gap:8px;
    }
    .game-toolbar{ display:flex; flex-wrap:wrap; gap:6px; margin-left:160px; flex:1; }
    .game-btn{
        border:0; padding:6px 10px; border-radius:8px;
        color:#fff; cursor:pointer; background:rgba(255,255,255,.15);
    }
    .game-btn:hover{ background:rgba(255,255,255,.25); }
    .game-overlay-close{
        border:0; background:rgba(255,255,255,.15); color:#fff;
        padding:6px 10px; border-radius:8px;
    }
    .game-badge{ color:#fff; font-size:13px; margin-left:8px; opacity:.9; min-width:120px; }

    .game-overlay-iframe{
        position:absolute; inset:0; width:100%; height:100%;
        border:0; background:#000;
        z-index:1;                      /* debajo del header */
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
        // Interceptamos cualquier <a> con nuestros data-* en /shop
        'click a[data-overlay-trigger]': '_onProductCardClick',
        'click a[data-product-url]': '_onProductCardClick',
    },

    start: function () {
        // Sniper para esperar productos
        console.log('Iniciando ProductIframe...');
        const productContainer = document.querySelector('.oe_website_sale .products_grid');
        if (productContainer) {
            // setTimeout(() => {
            //     // Simula la carga de productos después de 3 segundos
            //     const fakeProduct = document.createElement('div');
            //     fakeProduct.setAttribute('data-product-id', '999');
            //     productContainer.appendChild(fakeProduct);
            // }, 3000);
            const observer = new MutationObserver((mutations, obs) => {
                const products = productContainer.querySelectorAll('[data-product-id]');
                if (products.length > 0) {
                    console.log('Todos los productos cargados:', products.length);
                    document.querySelectorAll('a[data-product-url]').forEach(a => {
                        a.classList.remove('disabled');
                        a.style.pointerEvents = '';
                        a.style.opacity = '';
                    });
                    obs.disconnect();
                }
            });
            observer.observe(productContainer, { childList: true, subtree: true });
        }
        return this._super.apply(this, arguments);
    },

    // ======= Flags de control =======
    _overlayOpen: false,
    _squelchUntil: 0,
    _historyPushed: false,
    _popstateHandler: null,
    _disabledLinks: null,

    _shouldSquelchClicks() {
        return Date.now() < this._squelchUntil;
    },

    async _onProductCardClick(ev) {
        // Evitar doble disparo y doble overlay
        if (ev._handledByProductIframe) return;
        ev._handledByProductIframe = true;

        // Ignorar si overlay ya está abierto o en anti-rebote
        if (this._overlayOpen || this._shouldSquelchClicks()) {
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        // Permitir abrir en nueva pestaña con Ctrl/Meta/etc.
        if (ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;

        const a = ev.currentTarget;
        const productId = a.dataset.productId;
        const agencyId = a.dataset.agencyId;
        const userId = a.dataset.userId;
        const lang = a.dataset.lang || 'es';
        const iframeUrl = a.dataset.productUrl;

        console.log('Datos del producto:', { productId, agencyId, userId, lang, iframeUrl });
        if (!iframeUrl) return; // sin iframe_url -> navegación normal
        const baseIframeUrl = a.dataset.productUrl;
        // if (!baseIframeUrl || !agencyId) return; // sin datos -> navegación normal CHEQUEAR operatorID

        ev.preventDefault();
        ev.stopPropagation();

        const res = await rpc('/api/v1/get_token', { user_id: userId });
        const token = res.token;
        console.log('Token obtenido:', token);

        // Construir la URL con el token y otros parámetros
        const url = new URL(baseIframeUrl, window.location.origin);
        url.searchParams.set('token', res.token);
        url.searchParams.set('agencyId', agencyId);
        url.searchParams.set('operatorID', agencyId);
        url.searchParams.set('lang', lang);
        console.log('URL construida para el iframe:', url.toString());
        // Realizar petición fetch y mostrar resultado en consola
        try {
            const response = await fetch(url.toString());
            const result = await response.json();
            console.log('Resultado de la petición:', result);
        } catch (error) {
            console.error('Error en la petición:', error);
        }

        // Abrir el overlay con la URL construida
        if (!this._overlayOpen) {
            this._openOverlay(url.toString(), { productId, token, tracked: false });
        }
    },

    async _generateTokenForUser() {
        // return await rpc('/api/v1/get_token');
        return 'db8f24d5bd25fc9f89a800bb7d396624';
    },

    /* === Overlay fullscreen sin backdrop === */
    _openOverlay(iframeUrl, { productId = null, sessionId = null, tracked = true, balance = 0, token } = {}) {
        this._overlayOpen = true;

        // Desactivar temporalmente href de los enlaces de productos con iframe
        this._disableProductLinks();

        // Push history para que el botón "Atrás" cierre el overlay
        this._historyPushed = true;
        this._popstateHandler = () => {
            if (this._currentOverlay) {
                this._closeOverlay({ fromPopstate: true });
            }
        };
        window.addEventListener('popstate', this._popstateHandler);
        // Pusheamos un estado “virtual” del overlay
        history.pushState({ overlay: true }, '');

        // Root
        const root = document.createElement('div');
        root.className = 'game-overlay-root';

        // Header
        const header = document.createElement('div');
        header.className = 'game-overlay-header';

        // Toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'game-toolbar';

        // Acciones (mantener lógica/llamados tal cual)
        const btnLogin = this._makeBtn('🔐 Login', async () => {
            console.log('Presiono botón de Login');
            if (!productId) return alert('Producto no identificado.');
            try {
                console.log("Llamada a la api de login");
                // const token = prompt('Ingrese el Token:');
                // const res = await rpc('/api/v1/login', { token: token });
                const url = '/api/v1/login'
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token: token }),
                });
                const data = await res.json();
                console.log("Token obtenido:", data);

                if (res.error) return alert(res.error);
                console.log(`Response Login: ${JSON.stringify(res, null, 2)}`);
                alert(`Respuesta: ${JSON.stringify(data, null, 2)}`);
            } catch { alert('Error de red'); }
        });
        const btnWin = this._makeBtn('✅ Ganada', () => this._promptAndCall(sessionIdGetter(), '/api/v1/credit'));
        const btnLose = this._makeBtn('❌ Perdida', () => this._promptAndCall(sessionIdGetter(), '/api/v1/debit'));
        const btnRefund = this._makeBtn('↩️ Devolución', () => this._promptAndCall(sessionIdGetter(), '/api/v1/refund'));
        const btnBalance = this._makeBtn('💰 Balance', () => this._getBalance(sessionIdGetter(), '/api/v1/balance'));
        const btnEnd = this._makeBtn('🛑 Terminar', () => this._endSession(sessionIdGetter(), '/api/v1/end_game'));

        toolbar.append(btnLogin, btnWin, btnLose, btnRefund, btnBalance, btnEnd);

        // Badge
        const badge = document.createElement('span');
        badge.className = 'game-badge';
        badge.textContent = tracked ? `Saldo: ${(+balance).toFixed(2)}` : 'Sin sesión';

        // Cerrar
        const btnClose = document.createElement('button');
        btnClose.className = 'game-overlay-close';
        btnClose.type = 'button';
        btnClose.textContent = 'Cerrar';

        // Iframe
        const iframe = document.createElement('iframe');
        iframe.className = 'game-overlay-iframe';
        iframe.src = iframeUrl;
        iframe.allowFullscreen = true;

        header.append(toolbar, badge, btnClose);
        root.append(header, iframe);
        document.body.appendChild(root);

        // Estado del overlay
        const ov = this._currentOverlay = {
            root, header, toolbar, iframe, badge, btnClose,
            productId, sessionId, tracked,
        };

        // Registrar window en guard
        iframe.addEventListener('load', () => {
            try { window.__gameIframeWindows.add(iframe.contentWindow); } catch (e) { }
        });

        // Handlers de cierre (solo por la cruz)
        const closeHandler = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this._closeOverlay({ viaButton: true });
        };
        btnClose.addEventListener('click', closeHandler);

        // Bloquear scroll de la página
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(() => root.classList.add('show'));

        ov._handlers = { closeHandler, prevOverflow };

        // Utils con acceso al estado actual
        const sessionIdGetter = () => this._currentOverlay?.sessionId || null;

        this._updateBadge = (val) => {
            if (!this._currentOverlay?.badge) return;
            const s = this._currentOverlay.tracked ? `Saldo: ${(+val).toFixed(2)}` : 'Sin sesión';
            this._currentOverlay.badge.textContent = s;
        };

        this._promptAndCall = async (sid, url) => {
            // if (!this._currentOverlay?.tracked || !sid) return alert('No hay sesión activa. Hacé Login.');
            const raw = prompt('Ingrese monto:');
            const transactionId = prompt('Ingrese ID de transacción:');
            if (raw === null) return;
            const amount = parseFloat(String(raw).replace(',', '.'));
            if (Number.isNaN(amount) || amount < 0) return alert('Monto inválido');
            try {
                // const res = await rpc(url, { session_id: sid, token, gameId: 4, transactionId, amount });
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_id: sid, token: token, gameId: 4, transactionId: transactionId, amount: amount }),
                });
                const data = await res.json();
                console.log("Token obtenido:", data);

                if (res.error) return alert(res.error);
                console.log(`Response Debit / Credit: ${JSON.stringify(res, null, 2)}`);
                alert(`Respuesta: ${JSON.stringify(data, null, 2)}`);
                if (res.balance !== undefined) {
                    this._updateBadge(res.balance);
                }
            }
            catch { alert('Error de red'); }
        };

        this._getBalance = async (sid, url) => {
            try {
                // console.log('Get Balance - url: ', url);
                const res = await fetch(`/my/movimientos/balance?token=${encodeURIComponent(token)}`, {
                    method: 'POST',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token: token }),
                });
                const data = await res.json();
                console.log("Token obtenido:", data);

                // console.log(`Response Balance Actual: ${JSON.stringify(res, null, 2)}`);
                // alert(`Respuesta: ${JSON.stringify(data, null, 2)}`);
                const timestamp = Date.now();
                const enrichedData = {
                    ...data,
                    balance: Math.round(data.balance * 100),
                    timestamp
                };
                alert(`Respuesta: ${JSON.stringify(enrichedData, null, 2)}`);

                if (res.balance !== undefined) {
                    this._updateBadge(res.balance);
                }
            } catch { alert('Error de red'); }
        };

        this._endSession = async (sid, url) => {
            if (!this._currentOverlay?.tracked || !sid) {
                // alert('No hay sesión activa. El juego se cerrará.');
                alert('El juego se cerrará.');
            }
            else {
                const raw = prompt('Esta opción da por finalizado el juego. Ingrese monto:');
                // const transactionID = prompt('Ingrese ID de transacción:');
                if (raw === null) return;
                const amount = parseFloat(String(raw).replace(',', '.'));
                if (Number.isNaN(amount) || amount < 0) return alert('Monto inválido');
                try {
                    const res = await rpc(url, { session_id: sid, amount });
                    if (res.error) return alert(res.error);
                    console.log(`Fin del Juego: ${JSON.stringify(res, null, 2)}`);
                    alert(`Fin del juego: ${JSON.stringify(res, null, 2)}`)
                    if (res.balance !== undefined) {
                        this._updateBadge(res.balance);
                    }
                } catch { alert('Error de red'); }
            }
            // if (sid) rpc('/api/v1/end', { session_id: sid }).catch(() => { });
            this._closeOverlay({ viaButton: true });
        };

        return root;
    },

    _makeBtn(label, onClick) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'game-btn';
        b.textContent = label;
        b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onClick(); });
        return b;
    },

    _disableProductLinks() {
        // Quitar href para que un mouseup/click no dispare el link al cerrar
        this._disabledLinks = [];
        document.querySelectorAll('a[data-product-url]').forEach(a => {
            const href = a.getAttribute('href');
            this._disabledLinks.push([a, href]);
            if (href !== null) a.removeAttribute('href');
        });
    },

    _restoreProductLinks() {
        if (!this._disabledLinks) return;
        for (const [a, href] of this._disabledLinks) {
            if (href !== null && href !== undefined) a.setAttribute('href', href);
        }
        this._disabledLinks = null;
    },

    _teardownHistory({ fromPopstate = false, viaButton = false } = {}) {
        if (this._popstateHandler) {
            window.removeEventListener('popstate', this._popstateHandler);
            this._popstateHandler = null;
        }
        if (this._historyPushed) {
            // Si cerramos por botón, pedimos volver 1 estado (consume el overlay) sin navegar.
            if (viaButton && !fromPopstate) {
                try { history.back(); } catch { /* ignore */ }
            }
            this._historyPushed = false;
        }
    },

    _closeOverlay({ fromPopstate = false, viaButton = false } = {}) {
        const ov = this._currentOverlay;
        if (!ov) return;

        // Quitar del guard
        try { if (ov.iframe) window.__gameIframeWindows.delete(ov.iframe.contentWindow); } catch (e) { }

        // Restaurar scroll y eventos
        if (ov._handlers) {
            ov.btnClose.removeEventListener('click', ov._handlers.closeHandler);
            document.body.style.overflow = ov._handlers.prevOverflow || '';
        }

        // Restaurar href de los links
        this._restoreProductLinks();

        // History
        this._teardownHistory({ fromPopstate, viaButton });

        // Anti-rebote: ignorar clics por 400ms tras cerrar
        this._squelchUntil = Date.now() + 400;

        // Remover visualmente
        ov.root.classList.remove('show');
        setTimeout(() => ov.root.remove(), 150);
        this._currentOverlay = null;
        this._overlayOpen = false;
    },
});

export default publicWidget.registry.ProductIframe;
