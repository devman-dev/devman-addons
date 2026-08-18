/* ============================================================
   JogaJunto — Google Places Address Autocomplete
   ============================================================ */
(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") { fn(); return; }
        document.addEventListener("DOMContentLoaded", fn);
    }

    function setVal(id, value) {
        var el = document.getElementById(id);
        if (el && value && !el.value) {
            el.value = value;
        }
    }

    function setCountry(countryCode, countryName) {
        var sel = document.getElementById("jj_country_id");
        if (!sel || !countryCode) return;
        countryCode = countryCode.toUpperCase();
        for (var i = 0; i < sel.options.length; i++) {
            var opt = sel.options[i];
            if (opt.getAttribute("data-code") === countryCode ||
                opt.getAttribute("data-code2") === countryCode) {
                sel.value = opt.value;
                return;
            }
        }
        // Try to find by name if code didn't match
        if (countryName) {
            var lower = countryName.toLowerCase();
            for (var j = 0; j < sel.options.length; j++) {
                if (sel.options[j].text.toLowerCase().indexOf(lower) !== -1) {
                    sel.value = sel.options[j].value;
                    return;
                }
            }
        }
    }

    ready(function () {
        var input = document.getElementById("jj_street");
        var apiKey = document.getElementById("jj_places_config");
        if (!input || !apiKey) return;
        var key = apiKey.getAttribute("data-key");
        if (!key) return;

        var script = document.createElement("script");
        script.src = "https://maps.googleapis.com/maps/api/js?key="
                     + encodeURIComponent(key)
                     + "&loading=async&libraries=places&callback=jjInitPlaces";
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);

        window.jjInitPlaces = function () {
            try {
                var ac = new google.maps.places.Autocomplete(input, { types: ["address"] });

                ac.addListener("place_changed", function () {
                    var place = ac.getPlace();
                    if (!place || !place.address_components) return;

                    var comp = {};
                    for (var i = 0; i < place.address_components.length; i++) {
                        var c = place.address_components[i];
                        for (var j = 0; j < c.types.length; j++) {
                            comp[c.types[j]] = c;
                        }
                    }

                    // street_number
                    setVal("jj_street_number", comp.street_number ? comp.street_number.long_name : "");
                    // subpremise (complemento)
                    setVal("jj_street2", comp.subpremise ? comp.subpremise.long_name : "");
                    // locality / city
                    if (comp.locality) setVal("jj_city", comp.locality.long_name);
                    else if (comp.administrative_area_level_2) setVal("jj_city", comp.administrative_area_level_2.long_name);
                    // state
                    if (comp.administrative_area_level_1) {
                        var stateEl = document.getElementById("jj_state_name");
                        if (stateEl) stateEl.value = comp.administrative_area_level_1.long_name || "";
                    }
                    // country
                    if (comp.country) {
                        setCountry(comp.country.short_name, comp.country.long_name);
                    }
                    // zip
                    setVal("jj_zip", comp.postal_code ? comp.postal_code.long_name : "");
                    // district / neighborhood
                    if (comp.sublocality_level_1) setVal("jj_district", comp.sublocality_level_1.long_name);
                    else if (comp.neighborhood) setVal("jj_district", comp.neighborhood.long_name);
                });
            } catch (e) {
                console.warn("Google Places init error:", e);
            }
        };
    });
})();