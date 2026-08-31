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
        initFederationAccordions();
        initClubFormValidation();
        initToast();
        initInputMasksAndCounters();
        initStepNavigation();
        initFileUploads();
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

    /* FEDERATION_ACCORDION: accordion-based club picker with global search.
       Replaces pills + dropdown. Each federation is a clickable header that expands its clubs.
       Only one federation open at a time. Global search filters both fed headers and clubs. */
    function initFederationAccordions() {
        document.querySelectorAll(".jj-club-picker").forEach(function (picker) {
            var search = picker.querySelector(".jj-accordion-search");
            var hidden = picker.querySelector(".jj-club-value");
            var accordion = picker.querySelector(".jj-federation-accordion");
            var selectedBar = picker.querySelector(".jj-club-selected-bar");
            var clearBtn = picker.querySelector(".jj-club-clear");
            var items = Array.from(picker.querySelectorAll(".jj-accordion-item"));
            var options = Array.from(picker.querySelectorAll(".jj-club-option"));
            var emptyMsg = picker.querySelector(".jj-club-empty");
            if (!search || !hidden || !accordion) return;

            /* ----- helpers ----- */
            function escapeHtml(s) {
                return String(s)
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;");
            }

            function highlightText(text, query) {
                if (!query) return escapeHtml(text);
                var idx = String(text).toLowerCase().indexOf(query);
                if (idx < 0) return escapeHtml(text);
                return escapeHtml(String(text).slice(0, idx)) +
                    '<mark class="jj-club-hl">' +
                    escapeHtml(String(text).slice(idx, idx + query.length)) +
                    '</mark>' +
                    escapeHtml(String(text).slice(idx + query.length));
            }

            // Cache original copy text for highlight
            options.forEach(function (option) {
                var copy = option.querySelector(".jj-club-option-copy");
                if (!copy) return;
                var name = copy.querySelector("strong");
                var fed = copy.querySelector("small");
                option.__jjName = name ? name.textContent : "";
                option.__jjFed = fed ? fed.textContent : "";
            });

            function renderHighlight(query) {
                options.forEach(function (option) {
                    var copy = option.querySelector(".jj-club-option-copy");
                    if (!copy) return;
                    var name = copy.querySelector("strong");
                    var fed = copy.querySelector("small");
                    if (name) name.innerHTML = highlightText(option.__jjName, query);
                    if (fed) fed.innerHTML = highlightText(option.__jjFed, query);
                });
            }

            /* ----- accordion toggle ----- */
            function closeAll() {
                items.forEach(function (item) {
                    item.classList.remove("open");
                    var body = item.querySelector(".jj-accordion-body");
                    if (body) body.style.display = "none";
                });
            }

            function toggleItem(item) {
                var wasOpen = item.classList.contains("open");
                closeAll();
                if (!wasOpen) {
                    item.classList.add("open");
                    var body = item.querySelector(".jj-accordion-body");
                    if (body) {
                        body.style.display = "";
                        // Staggered fade-in for club options
                        var chips = body.querySelectorAll(".jj-club-option");
                        chips.forEach(function(chip, i) {
                            chip.style.animation = "none";
                            chip.offsetHeight; // trigger reflow
                            chip.classList.add("stagger-in");
                            chip.style.animation = "";
                            chip.style.animationDelay = (i * 50) + "ms";
                        });
                    }
                    // Scroll to top of the opened body
                    item.scrollIntoView({ block: "nearest", behavior: "smooth" });
                }
            }

            items.forEach(function (item) {
                var header = item.querySelector(".jj-accordion-header");
                if (!header) return;
                header.addEventListener("click", function () {
                    toggleItem(item);
                });
            });

            /* ----- global search (fed + club) ----- */
            search.addEventListener("input", function () {
                var query = search.value.trim().toLowerCase();
                var anyVisible = false;

                items.forEach(function (item) {
                    var fedSearch = (item.querySelector(".jj-accordion-header") || {}).dataset
                        ? (item.querySelector(".jj-accordion-header").dataset.fedSearch || "")
                        : "";
                    var fedMatch = !query || fedSearch.indexOf(query) >= 0;
                    var clubOptions = Array.from(item.querySelectorAll(".jj-club-option"));
                    var clubVisible = 0;

                    clubOptions.forEach(function (opt) {
                        var visible = !query || (opt.dataset.search || "").indexOf(query) >= 0;
                        opt.hidden = !visible;
                        if (visible) clubVisible++;
                    });

                    // Show item if fed name matches OR any club matches
                    var showItem = fedMatch || clubVisible > 0;
                    item.hidden = !showItem;
                    if (showItem) anyVisible = true;

                    // Auto-expand if searching and there's a match
                    if (query && showItem) {
                        item.classList.add("open");
                        var body = item.querySelector(".jj-accordion-body");
                        if (body) body.style.display = "";
                    } else if (!query) {
                        item.classList.remove("open");
                        var body2 = item.querySelector(".jj-accordion-body");
                        if (body2) body2.style.display = "none";
                    }
                });

                renderHighlight(query);
                if (emptyMsg) emptyMsg.hidden = anyVisible;
            });

            /* ----- selection ----- */
            function selectOption(option) {
                if (!option) return;
                hidden.value = option.dataset.id;
                // Update the selected bar
                var badge = option.querySelector(".jj-club-option-badge");
                var selectedLeft = picker.querySelector(".jj-club-selected-left");
                if (selectedLeft) {
                    if (badge) {
                        var existingBadge = selectedLeft.querySelector(".jj-club-selected-badge");
                        if (existingBadge) existingBadge.replaceWith(badge.cloneNode(true));
                    }
                    var selectedName = picker.querySelector(".jj-club-selected-name");
                    if (selectedName) selectedName.textContent = option.dataset.name;
                }
                if (selectedBar) selectedBar.style.display = "";

                options.forEach(function (item) {
                    item.classList.toggle("selected", item === option);
                });

                // Badge bounce animation
                var optionBadge = option.querySelector(".jj-club-option-badge");
                if (optionBadge) {
                    optionBadge.classList.add("bounce");
                    setTimeout(function() {
                        optionBadge.classList.remove("bounce");
                    }, 300);
                }
                // Celebration glow animation
                option.classList.add("celebrate");
                setTimeout(function () {
                    option.classList.remove("celebrate");
                }, 600);
            }

            function clearSelection() {
                hidden.value = "";
                if (selectedBar) selectedBar.style.display = "none";
                options.forEach(function (item) {
                    item.classList.remove("selected");
                });
                search.focus();
            }

            options.forEach(function (option) {
                option.addEventListener("click", function () {
                    selectOption(option);
                });
            });

            if (clearBtn) {
                clearBtn.addEventListener("click", function () {
                    clearSelection();
                });
            }

            /* ----- Auto-expand federation containing preselected club ----- */
            if (hidden.value) {
                var preselected = options.filter(function (o) {
                    return o.dataset.id === hidden.value;
                })[0];
                if (preselected) {
                    var item = preselected.closest(".jj-accordion-item");
                    if (item) {
                        item.classList.add("open");
                        var body = item.querySelector(".jj-accordion-body");
                        if (body) body.style.display = "";
                    }
                }
            }

            /* ----- LOTE 2+1: auto-scroll to selected on search focus ----- */
            search.addEventListener("focus", function () {
                var selId = hidden.value;
                if (selId) {
                    var selOption = picker.querySelector('.jj-club-option[data-id="' + selId + '"]');
                    if (selOption) {
                        var item = selOption.closest(".jj-accordion-item");
                        if (item) {
                            item.hidden = false;
                            item.classList.add("open");
                            var body = item.querySelector(".jj-accordion-body");
                            if (body) body.style.display = "";
                        }
                        selOption.hidden = false;
                        setTimeout(function () {
                            selOption.scrollIntoView({ block: "center", behavior: "smooth" });
                            selOption.classList.add("jj-flash-once");
                            setTimeout(function () { selOption.classList.remove("jj-flash-once"); }, 800);
                        }, 100);
                    }
                }
            });

            /* ----- LOTE 2+1: TUS CLUBES chips ----- */
            var modalityBody = picker.closest(".jj-modality-body");
            if (modalityBody) {
                modalityBody.querySelectorAll(".jj-myclub-chip").forEach(function (chip) {
                    chip.addEventListener("click", function () {
                        var clubId = chip.dataset.id;
                        var option = picker.querySelector('.jj-club-option[data-id="' + clubId + '"]');
                        if (!option) return;
                        // Expand the federation containing this club
                        var item = option.closest(".jj-accordion-item");
                        if (item) {
                            item.hidden = false;
                            closeAll();
                            item.classList.add("open");
                            var body = item.querySelector(".jj-accordion-body");
                            if (body) body.style.display = "";
                        }
                        option.hidden = false;
                        selectOption(option);
                        // Scroll to the option
                        setTimeout(function () {
                            option.scrollIntoView({ block: "center", behavior: "smooth" });
                        }, 80);
                    });
                });

                /* ----- LOTE 2: popular chips ----- */
                modalityBody.querySelectorAll(".jj-popular-chip").forEach(function (chip) {
                    chip.addEventListener("click", function () {
                        var clubId = chip.dataset.id;
                        var option = picker.querySelector('.jj-club-option[data-id="' + clubId + '"]');
                        if (!option) return;
                        var item = option.closest(".jj-accordion-item");
                        if (item) {
                            item.hidden = false;
                            closeAll();
                            item.classList.add("open");
                            var body = item.querySelector(".jj-accordion-body");
                            if (body) body.style.display = "";
                        }
                        option.hidden = false;
                        selectOption(option);
                        setTimeout(function () {
                            option.scrollIntoView({ block: "center", behavior: "smooth" });
                        }, 80);
                    });
                });
            }
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

    /* ============================================================
       INPUT MASKS & CHARACTER COUNTERS
       CPF (11 digits) and Telefone (11 digits) — auto-format
       plus a golden character counter below the input
       ============================================================ */
    function initInputMasksAndCounters() {
        var cpf = document.getElementById("jj_cpf");
        var phone = document.getElementById("jj_telefone");

        if (cpf) {
            attachCharCounter(cpf, 11);
            cpf.addEventListener("input", function () {
                cpf.value = maskCPF(cpf.value);
                updateCharCounter(cpf);
            });
        }
        if (phone) {
            attachCharCounter(phone, 11);
            phone.addEventListener("input", function () {
                phone.value = maskPhone(phone.value);
                updateCharCounter(phone);
            });
        }
    }

    function maskCPF(v) {
        v = v.replace(/\D/g, "").slice(0, 11);
        return v
            .replace(/(\d{3})(\d)/, "$1.$2")
            .replace(/(\d{3})(\d)/, "$1.$2")
            .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
    }

    function maskPhone(v) {
        v = v.replace(/\D/g, "").slice(0, 11);
        if (v.length <= 2) return v;
        if (v.length <= 6) return "(" + v.slice(0, 2) + ") " + v.slice(2);
        if (v.length <= 10) return "(" + v.slice(0, 2) + ") " + v.slice(2, 6) + "-" + v.slice(6);
        return "(" + v.slice(0, 2) + ") " + v.slice(2, 7) + "-" + v.slice(7);
    }

    function attachCharCounter(input, max) {
        var field = input.closest(".jj-field");
        if (!field) return;
        // Phone input is inside .jj-phone-wrap — still fine, counter goes on the field
        var counter = document.createElement("span");
        counter.className = "jj-char-counter";
        counter.setAttribute("data-max", max);
        counter.textContent = "0/" + max;
        field.appendChild(counter);
        input.setAttribute("data-char-max", max);
        updateCharCounter(input);
    }

    function updateCharCounter(input) {
        var field = input.closest(".jj-field");
        if (!field) return;
        var counter = field.querySelector(".jj-char-counter");
        if (!counter) return;
        var max = parseInt(counter.getAttribute("data-max"), 10) || 11;
        var digits = input.value.replace(/\D/g, "");
        counter.textContent = digits.length + "/" + max;
        if (digits.length >= max) {
            counter.classList.add("complete");
        } else {
            counter.classList.remove("complete");
        }
    }


    /* ============================================================
       FILE UPLOAD DROP-ZONES (CIN Frente/Verso)
       Live preview + drag & drop + filename display
       ============================================================ */
    function initFileUploads() {
        var wraps = document.querySelectorAll(".jj-file-upload-wrap");
        if (!wraps.length) return;

        wraps.forEach(function (wrap) {
            var input = wrap.querySelector(".jj-file-input");
            var label = wrap.querySelector(".jj-file-label");
            if (!input || !label) return;

            var placeholder = label.querySelector(".jj-file-placeholder");
            if (placeholder && placeholder.textContent.trim() === "Selecionar arquivo") {
                placeholder.textContent = "Clique ou arraste o arquivo";
            }

            var preview = document.createElement("img");
            preview.className = "jj-file-preview-img";
            label.insertBefore(preview, label.firstChild);

            function showFile(file) {
                if (!file) return;
                label.classList.add("has-file");
                if (placeholder) {
                    placeholder.textContent = file.name.length > 24
                        ? file.name.slice(0, 22) + "\u2026"
                        : file.name;
                }
                if (file.type && file.type.indexOf("image/") === 0) {
                    var reader = new FileReader();
                    reader.onload = function (e) {
                        preview.src = e.target.result;
                    };
                    reader.readAsDataURL(file);
                }
            }

            input.addEventListener("change", function () {
                if (input.files && input.files.length) {
                    showFile(input.files[0]);
                }
            });

            ["dragenter", "dragover"].forEach(function (evName) {
                label.addEventListener(evName, function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    label.classList.add("is-dragover");
                });
            });

            ["dragleave", "drop"].forEach(function (evName) {
                label.addEventListener(evName, function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    label.classList.remove("is-dragover");
                });
            });

            label.addEventListener("drop", function (e) {
                if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                    input.files = e.dataTransfer.files;
                    var evt = document.createEvent("HTMLEvents");
                    evt.initEvent("change", false, true);
                    input.dispatchEvent(evt);
                }
            });
        });
    }

    /* Export showToast for inline use */
    window.JJ = window.JJ || {};
    window.JJ.showToast = showToast;
})();
