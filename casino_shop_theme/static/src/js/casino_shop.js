/* ═══════════════════════════════════════════════════════════════════
   casino_shop_theme — Casino Lobby JavaScript
   Handles: carousel navigation, search, category filtering, mobile swipe
   ═══════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    /* ── CAROUSEL SCROLL ── */
    window.casinoScroll = function (btn, direction) {
        var wrap = btn.closest('.casino_carousel_wrap');
        if (!wrap) return;
        var carousel = wrap.querySelector('.casino_carousel');
        if (!carousel) return;
        var card = carousel.querySelector('.casino_card');
        if (!card) return;
        var cardWidth = card.offsetWidth + 16; /* card + gap */
        carousel.scrollBy({ left: direction * cardWidth * 3, behavior: 'smooth' });
    };

    /* ── CATEGORY PILLS — filter sections ── */
    var pills = document.querySelectorAll('.casino_cat_pill');
    var sections = document.querySelectorAll('.casino_section');

    pills.forEach(function (pill) {
        pill.addEventListener('click', function () {
            var cat = this.dataset.cat;

            /* Update active pill */
            pills.forEach(function (p) { p.classList.remove('active'); });
            this.classList.add('active');

            /* Show/hide sections */
            sections.forEach(function (sec) {
                if (cat === 'all' || sec.dataset.category === cat) {
                    sec.style.display = '';
                } else {
                    sec.style.display = 'none';
                }
            });
        });
    });

    /* ── SEARCH FILTER ── */
    var searchInput = document.getElementById('casino_search');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var query = this.value.toLowerCase().trim();

            sections.forEach(function (sec) {
                var cards = sec.querySelectorAll('.casino_card:not(.casino_card_placeholder)');
                var anyVisible = false;

                cards.forEach(function (card) {
                    var name = (card.querySelector('.casino_card_name') || {}).textContent || '';
                    var provider = (card.querySelector('.casino_card_provider') || {}).textContent || '';
                    var text = (name + ' ' + provider).toLowerCase();

                    if (!query || text.indexOf(query) !== -1) {
                        card.classList.remove('hidden');
                        anyVisible = true;
                    } else {
                        card.classList.add('hidden');
                    }
                });

                /* Show section if it has visible cards or is "all" */
                if (sec.dataset.category === 'all') {
                    sec.style.display = '';
                } else if (anyVisible) {
                    sec.style.display = '';
                } else {
                    sec.style.display = 'none';
                }
            });
        });
    }

    /* ── MOBILE SWIPE ── */
    var carousels = document.querySelectorAll('.casino_carousel');
    carousels.forEach(function (carousel) {
        var startX = 0, startScroll = 0, isDragging = false;

        carousel.addEventListener('touchstart', function (e) {
            startX = e.touches[0].clientX;
            startScroll = carousel.scrollLeft;
            isDragging = true;
        }, { passive: true });

        carousel.addEventListener('touchmove', function (e) {
            if (!isDragging) return;
            var dx = startX - e.touches[0].clientX;
            carousel.scrollLeft = startScroll + dx;
        }, { passive: true });

        carousel.addEventListener('touchend', function () {
            isDragging = false;
        });
    });
});