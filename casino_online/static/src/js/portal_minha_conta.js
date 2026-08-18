/* ═══════════════════════════════════════════════════════
   Minha Conta — Panel navigation & mobile behavior
   ═══════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var ACTIVE_CLASS = 'active';
    var SECTION_PREFIX = '#';

    /**
     * Get the current hash section name from URL (strip #)
     */
    function getHashSection() {
        return (window.location.hash || '').replace('#', '');
    }

    /**
     * Find the panel element for a section name
     */
    function getPanel(name) {
        return name ? document.getElementById(name) : null;
    }

    /**
     * Find all sidebar nav links referencing a data-section
     */
    function getSidebarLinks() {
        return document.querySelectorAll('.jj-mc-sidebar .jj-mc-nav-item[data-section]');
    }

    /**
     * Find all bottom-nav links
     */
    function getBottomNavLinks() {
        return document.querySelectorAll('.jj-mc-bottom-nav .jj-mc-bnav-item[data-section]');
    }

    /**
     * Deactivate all panels, activate the target one.
     */
    function switchToPanel(name) {
        var panels = document.querySelectorAll('.jj-mc-panel');
        panels.forEach(function (p) { p.classList.remove(ACTIVE_CLASS); });

        var target = getPanel(name);
        if (target) {
            target.classList.add(ACTIVE_CLASS);
        }
    }

    /**
     * Sync active class across sidebar and bottom nav items.
     */
    function syncNavActive(name) {
        var selector = '[data-section="' + name + '"]';
        var allLinks = document.querySelectorAll(
            '.jj-mc-sidebar .jj-mc-nav-item[data-section], ' +
            '.jj-mc-bottom-nav .jj-mc-bnav-item[data-section]'
        );

        allLinks.forEach(function (link) {
            link.classList.remove(ACTIVE_CLASS);
        });

        var matching = document.querySelectorAll(
            '.jj-mc-sidebar .jj-mc-nav-item' + selector + ', ' +
            '.jj-mc-bottom-nav .jj-mc-bnav-item' + selector
        );
        matching.forEach(function (link) {
            link.classList.add(ACTIVE_CLASS);
        });
    }

    /**
     * Navigate to a section: switch panel, sync nav, update URL hash.
     */
    function navigateTo(name) {
        if (!name) return;
        switchToPanel(name);
        syncNavActive(name);

        // Update hash without triggering hashchange (replace state)
        var newHash = SECTION_PREFIX + name;
        if (window.location.hash !== newHash) {
            history.replaceState(null, '', newHash);
        }

        // Close mobile sidebar if open
        var container = document.querySelector('.jj-minha-conta');
        if (container) {
            container.classList.remove('sidebar-open');
        }
    }

    /**
     * Bind click events to sidebar nav links.
     */
    function bindSidebarNav() {
        getSidebarLinks().forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                var section = this.getAttribute('data-section');
                if (section) {
                    navigateTo(section);
                } else {
                    // Handle real links like Sair (/web/session/logout)
                    var href = this.getAttribute('href');
                    if (href && href !== SECTION_PREFIX && !href.startsWith('#')) {
                        window.location.href = href;
                    }
                }
            });
        });
    }

    /**
     * Bind click events to bottom nav links.
     */
    function bindBottomNav() {
        getBottomNavLinks().forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                var section = this.getAttribute('data-section');
                if (section) {
                    navigateTo(section);
                }
            });
        });
    }

    /**
     * Handle initial load: read URL hash to determine active section.
     */
    function initFromHash() {
        var section = getHashSection();
        if (section && getPanel(section)) {
            navigateTo(section);
        } else {
            // Default to first panel
            var firstPanel = document.querySelector('.jj-mc-panel');
            if (firstPanel) {
                var defaultSection = firstPanel.id;
                navigateTo(defaultSection);
            }
        }
    }

    /**
     * Handle history back/forward (hashchange).
     */
    function bindHashChange() {
        window.addEventListener('hashchange', function () {
            var section = getHashSection();
            if (section && getPanel(section)) {
                switchToPanel(section);
                syncNavActive(section);
            }
        });
    }

    /**
     * Bind overlay click to close mobile sidebar.
     */
    function bindOverlay() {
        var overlay = document.querySelector('.jj-mc-overlay');
        if (overlay) {
            overlay.addEventListener('click', function () {
                var container = document.querySelector('.jj-minha-conta');
                if (container) {
                    container.classList.remove('sidebar-open');
                }
            });
        }
    }

    /**
     * Bind menu toggle for mobile.
     */
    function bindMenuToggle() {
        var toggle = document.querySelector('.jj-mc-menu-toggle');
        if (toggle) {
            toggle.addEventListener('click', function () {
                var container = document.querySelector('.jj-minha-conta');
                if (container) {
                    container.classList.toggle('sidebar-open');
                }
            });
        }
    }

    /** Fix: handle real-link nav items (e.g., deposit/withdraw links inside nav) */
    function fixRealLinks() {
        // Sidebar CTA buttons — let them navigate normally
        var ctaLinks = document.querySelectorAll('.jj-mc-sidebar-cta a');
        ctaLinks.forEach(function (link) {
            link.addEventListener('click', function (e) {
                // Let normal navigation proceed
            });
        });
    }

    /** Close mobile sidebar on Escape key */
    function bindEscape() {
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                var container = document.querySelector('.jj-minha-conta');
                if (container) {
                    container.classList.remove('sidebar-open');
                }
            }
        });
    }

    /* ── Init ── */
    function init() {
        bindSidebarNav();
        bindBottomNav();
        bindHashChange();
        bindOverlay();
        bindMenuToggle();
        bindEscape();
        fixRealLinks();
        initFromHash();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();