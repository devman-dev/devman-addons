/* ============================================================
   JogaJunto — Portal Club Support JavaScript
   Odoo 18 native — no frameworks
   ============================================================ */

(function () {
    "use strict";

    /* ----- DOM ready ----- */
    function ready(fn) {
        if (document.readyState !== "loading") {
            fn();
        } else {
            document.addEventListener("DOMContentLoaded", fn);
        }
    }

    ready(function () {
        initClubTiles();
        initFederationClubPickers();
        initClubFormValidation();
        initToast();
        initStepNavigation();
    });

    /* ============================================================
       CLUB TILE SELECTION
       Enhances radio buttons wrapped in .jj-club-tile labels
       Works as progressive enhancement — no-JS fallback uses radios
       ============================================================ */
    function initClubTiles() {
        var tiles = document.querySelectorAll(".jj-club-tile");
        if (!tiles.length) return;

        tiles.forEach(function (tile) {
            var radio = tile.querySelector('input[type="radio"]');
            if (!radio) return;

            // Sync initial state
            updateTileState(tile, radio);

            tile.addEventListener("click", function (e) {
                // If clicking the radio itself, let native behavior handle it
                if (e.target.tagName === "INPUT") return e.stopPropagation();

                // Select this radio
                radio.checked = true;

                // Unselect siblings in same category
                var container = tile.closest(".jj-club-tiles");
                if (container) {
                    var allTiles = container.querySelectorAll(".jj-club-tile");
                    allTiles.forEach(function (t) {
                        var r = t.querySelector('input[type="radio"]');
                        if (r) {
                            updateTileState(t, r);
                        }
                    });
                }
            });

            radio.addEventListener("change", function () {
                var container = tile.closest(".jj-club-tiles");
                if (container) {
                    var allTiles = container.querySelectorAll(".jj-club-tile");
                    allTiles.forEach(function (t) {
                        var r = t.querySelector('input[type="radio"]');
                        if (r) {
                            updateTileState(t, r);
                        }
                    });
                }
            });
        });
    }

    function updateTileState(tile, radio) {
        if (radio.checked) {
            tile.classList.add("selected");
        } else {
            tile.classList.remove("selected");
        }
    }

    /* FEDERATION_CLUB_PICKER: searchable, federation-grouped club fields. */
    function initFederationClubPickers() {
        document.querySelectorAll(".jj-club-picker").forEach(function (picker) {
            var search = picker.querySelector(".jj-club-search");
            var hidden = picker.querySelector(".jj-club-value");
            var dropdown = picker.querySelector(".jj-club-dropdown");
            var clear = picker.querySelector(".jj-club-clear");
            var options = Array.from(picker.querySelectorAll(".jj-club-option"));
            if (!search || !hidden || !dropdown) return;

            function filterOptions() {
                var query = search.value.trim().toLowerCase();
                var visibleCount = 0;
                options.forEach(function (option) {
                    var visible = !query || (option.dataset.search || "").indexOf(query) >= 0;
                    option.hidden = !visible;
                    if (visible) visibleCount += 1;
                });
                picker.querySelectorAll(".jj-club-group").forEach(function (group) {
                    group.hidden = !group.querySelector(".jj-club-option:not([hidden])");
                });
                var empty = picker.querySelector(".jj-club-empty");
                if (empty) empty.hidden = visibleCount !== 0;
                dropdown.classList.add("open");
            }

            search.addEventListener("focus", filterOptions);
            search.addEventListener("input", function () {
                hidden.value = "";
                picker.classList.remove("selected");
                filterOptions();
            });
            options.forEach(function (option) {
                option.addEventListener("click", function () {
                    hidden.value = option.dataset.id;
                    search.value = option.dataset.name;
                    picker.classList.add("selected");
                    options.forEach(function (item) {
                        item.classList.toggle("selected", item === option);
                    });
                    dropdown.classList.remove("open");
                });
            });
            clear.addEventListener("click", function () {
                hidden.value = "";
                search.value = "";
                picker.classList.remove("selected");
                options.forEach(function (item) { item.classList.remove("selected"); });
                search.focus();
            });
            picker.addEventListener("focusout", function (event) {
                if (!picker.contains(event.relatedTarget)) {
                    dropdown.classList.remove("open");
                }
            });
            if (hidden.value) picker.classList.add("selected");
        });
    }

    /* ============================================================
       CLUB FORM VALIDATION
       Checks require_selection categories have a club chosen
       ============================================================ */
    function initClubFormValidation() {
        var form = document.getElementById("jj_clubs_form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            var modalityCards = form.querySelectorAll(".jj-modality-card");
            var missing = [];

            modalityCards.forEach(function (card) {
                if (card.dataset.required !== "1") return;
                var selected = card.querySelector(".jj-club-value");
                var hasSelection = selected && selected.value;
                if (!hasSelection) {
                    var categoryName = "";
                    var titleEl = card.querySelector(".jj-modality-info h4");
                    if (titleEl) categoryName = titleEl.textContent.trim();
                    missing.push(categoryName || "Categoria");
                }
            });

            if (missing.length > 0) {
                e.preventDefault();
                showToast(
                    "⚠ Selecione um clube em: " + missing.join(", "),
                    true
                );
                // Scroll to first missing category
                var firstMissing = form.querySelector(".jj-modality-card");
                if (firstMissing) {
                    firstMissing.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            }
        });
    }

    /* ============================================================
       TOAST NOTIFICATION
       Auto-show if element exists, auto-hide after delay
       ============================================================ */
    function initToast() {
        var toast = document.getElementById("jj_toast");
        if (!toast) return;

        // Show with animation
        setTimeout(function () {
            toast.classList.add("show");
        }, 300);

        // Auto-hide after 5 seconds
        setTimeout(function () {
            toast.classList.remove("show");
        }, 5300);
    }

    function showToast(message, isError) {
        var toast = document.getElementById("jj_toast");
        if (!toast) {
            // Create toast on the fly
            toast = document.createElement("div");
            toast.id = "jj_toast";
            toast.className = "jj-toast" + (isError ? " jj-toast-error" : "");
            toast.innerHTML =
                '<div class="jj-toast-icon">' +
                (isError ? "!" : "✓") +
                "</div>" +
                message;
            document.body.appendChild(toast);
        } else {
            var icon = toast.querySelector(".jj-toast-icon");
            if (icon) icon.textContent = isError ? "!" : "✓";
            toast.className = "jj-toast" + (isError ? " jj-toast-error" : "");
            toast.lastChild && toast.lastChild.nodeType === 3
                ? (toast.lastChild.textContent = message)
                : (toast.querySelector(".jj-toast-icon").nextSibling.textContent = message);
        }

        // Force reflow for animation
        toast.offsetHeight;

        setTimeout(function () {
            toast.classList.add("show");
            if (isError) toast.style.background = "#dc2626";
            else toast.style.background = "";
        }, 100);

        setTimeout(function () {
            toast.classList.remove("show");
        }, 5000);
    }

    /* ============================================================
       STEP NAVIGATION — keyboard support, mobile tweaks
       ============================================================ */
    function initStepNavigation() {
        // Focus first input on Step 1
        var firstInput = document.querySelector("#jj_name, #jj_register_form input:first-of-type");
        if (firstInput && !window.location.pathname.includes("/clubs")) {
            setTimeout(function () {
                firstInput.focus();
            }, 500);
        }

        // Keyboard: Enter on club tiles works via radio change
        document.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && document.activeElement) {
                var tile = document.activeElement.closest(".jj-club-tile");
                if (tile) {
                    e.preventDefault();
                    tile.click();
                }
            }
        });
    }

    /* Export showToast for inline use */
    window.JJ = window.JJ || {};
    window.JJ.showToast = showToast;
})();
