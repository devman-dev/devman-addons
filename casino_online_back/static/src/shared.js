/**
 * ASADITO Casino — shared.js
 * Cliente de APIs, sesión, navegación y utilidades comunes.
 * Cargado por las 7 vistas HTML independientes.
 */

// ——— CONFIG ———
var ODOO_BASE = 'https://asadito2.asartorio.online';
var ODOO_DB   = 'asadito2.asartorio.online';

// ——— STATE ———
var session  = null;   // resultado de /web/session/authenticate
var balance  = null;   // resultado de /casino/balance
var profile  = null;   // resultado de /casino/profile

// ——— HELPERS ———
function el(id){ return document.getElementById(id); }
function esc(s){ if(!s)return''; var d=document.createElement('div');d.textContent=s;return d.innerHTML; }
function fmt$(v){ return '$'+(Number(v)||0).toFixed(2); }
function cls(o){ return (Number(o)||0)>=0 ? 'mv-pos':'mv-neg'; }
function sign(v){ var n=Number(v)||0; return n>=0?'+'+n.toFixed(2):n.toFixed(2); }

// ——— LOADING / TOAST (injectable) ———
function showLoading(msg){
  var ol = el('loadingOverlay'), lt = el('loadingText');
  if(ol&&lt){ lt.textContent=msg||'Cargando…'; ol.classList.add('show'); }
}
function hideLoading(){
  var ol = el('loadingOverlay'); if(ol) ol.classList.remove('show');
}
var toastTimer;
function toast(msg,isErr){
  var t = el('appToast'); if(!t) return;
  t.textContent = msg; t.style.color = isErr ? 'var(--crimson,#ff4d5e)' : 'var(--ink,#ffffff)';
  t.classList.add('show'); clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ t.classList.remove('show'); }, 4200);
}

// ——— API ———
function api(path, body){
  return fetch(ODOO_BASE + path, {
    method:'POST', credentials:'include',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body===undefined ? {} : body)
  }).then(function(r){
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(function(d){
    if(d.error){
      // SESSION_EXPIRED — código 100 de Odoo o mensaje "Odoo Session Expired"
      if(d.error.code === 100 || d.error.message === 'Odoo Session Expired'){
        clearSession();
        window.location.replace(ODOO_BASE + '/');
        throw new Error('SESSION_EXPIRED');
      }
      throw new Error(d.error.message || (d.error.data&&d.error.data.message) || 'Error de API');
    }
    return d.result !== undefined && d.result !== null ? d.result : d;
  });
}

// ——— SESSION ———
function getSession(){
  try{ return JSON.parse(sessionStorage.getItem('asadito_session')); }catch(e){ return null; }
}
function setSession(s){ sessionStorage.setItem('asadito_session', JSON.stringify(s)); }
function clearSession(){ sessionStorage.removeItem('asadito_session'); session=balance=profile=null; }

// ——— AUTH CHECK ———
// Si no hay sesión guardada, redirige a login (solo en páginas protegidas)
function requireAuth(){
  var s = getSession();
  if (!s || !s.uid) {
    window.location.replace(ODOO_BASE + '/');
    return false;
  }
  session = s;
  return true;
}

// ——— LOGIN ———
function doLogin(email, pass, btnEl, errEl){
  if(btnEl) btnEl.disabled = true;
  api('/web/session/authenticate', {
    jsonrpc:'2.0', method:'call',
    params: { db: ODOO_DB, login: email, password: pass }
  }).then(function(r){
    setSession(r);
    session = r;
    window.location.replace(ODOO_BASE + '/casino');
  }).catch(function(e){
    if(errEl){ errEl.textContent = 'Email o contraseña incorrectos'; errEl.style.display='block'; }
    if(btnEl) btnEl.disabled = false;
  });
}

// ——— LOGOUT ———
function adLogout(){
  clearSession();
  // Navegar al home de Odoo, no al login de casino
  window.location.href = ODOO_BASE + '/';
}

// ——— DATA FETCHERS (con cache interno) ———

function loadBalance(){
  return api('/casino/balance').then(function(r){
    balance = r; return r;
  });
}

function loadProfile(){
  return api('/casino/profile').then(function(r){
    profile = r; return r;
  });
}

function loadGames(){
  return api('/casino/games').then(function(r){
    return r;
  });
}

function loadMovements(opts){
  opts = opts || {};
  var params = {
    page:        opts.page || 1,
    page_size:   opts.page_size || 20
  };
  if (opts.type) params.type = opts.type;
  if (opts.direction) params.direction = opts.direction;
  return api('/casino/transactions', params);
}

function getGameById(id){
  return api('/casino/games').then(function(r){
    return (r.games||[]).find(function(g){ return String(g.id)===String(id); }) || null;
  });
}

// ——— HEADER RENDER (usado por vistas autenticadas) ———
function renderTopBar(){
  var bar = el('topBar'); if(!bar) return;
  bar.style.display = 'flex';
  var av    = el('playerAv');
  var nameC = el('playerNameChip');
  var balC  = el('playerBalanceChip');
  var s     = getSession();
  if(s && av)    av.textContent = (s.name||'J')[0].toUpperCase();
  if(s && nameC) nameC.textContent = s.name || 'Jugador';
  // Balance se actualiza aparte con refreshBalance()
}

function refreshBalance(){
  var balEl = el('playerBalanceChip');
  if(!balEl) return;
  loadBalance().then(function(b){
    if(balEl) balEl.textContent = fmt$(b.wallet_balance);
  }).catch(function(){});
}

// ——— INIT COMÚN (páginas post-login) ———
function initAuthedPage(){
  if(!requireAuth()) return false;
  renderTopBar();
  refreshBalance();
  return true;
}

// --- THEME: ASADITO ---
// Se espera que cada vista defina su <style> con estas variables (o cargue shared.css):
// :root{--bg-deep:#050a18; --bg-mid:#09122b; --bg-card:rgba(4,8,20,0.7); --border:rgba(255,255,255,0.08);
//   --primary:#2563eb; --primary-dim:#1a56d0; --gold:#f2c451; --gold-dim:#b8912a;
//   --crimson:#ff4d5e; --ink:#ffffff; --muted:#94a3b8; --radius:16px}

// --- ODOO NATIVE LIVE CHAT WIDGET ---
(function initLivechat(){
  window.odoo = window.odoo || {};
  window.odoo.__session_info__ = window.odoo.__session_info__ || {};
  window.odoo.__session_info__.livechatData = {
    isAvailable: true,
    serverUrl: '',
    options: {
      header_background_color: '#2563eb',
      button_background_color: '#2563eb',
      title_color: '#FFFFFF',
      button_text_color: '#FFFFFF',
      button_text: '¿Necesitás ayuda?',
      default_message: '¡Hola! ¿En qué podemos ayudarte?',
      channel_name: 'Soporte ASADITO',
      channel_id: 1,
      default_username: 'Jugador'
    }
  };
  var s = document.createElement('script');
  s.src = '/im_livechat/external_lib.js';
  s.async = true;
  document.head.appendChild(s);
})();