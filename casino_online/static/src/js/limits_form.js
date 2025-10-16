(function () {
    var nf = new Intl.NumberFormat(navigator.language || 'es-AR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        useGrouping: false
    });

    function parseLocale(s) {
        if (s === null || s === undefined) return NaN;
        s = String(s).trim();
        if (!s) return NaN;

        var sample = nf.format(1.1);
        var dec = sample.match(/[.,]/)?.[0] || '.';
        var group = (dec === '.') ? ',' : '.';

        s = s.replace(new RegExp('\\' + group, 'g'), '');
        if (dec !== '.') s = s.replace(new RegExp('\\' + dec, 'g'), '.');

        return Number(s);
    }

    function toNumber(v) { return parseLocale(v); }

    function isValid(n) { return !isNaN(n) && isFinite(n) && n >= 0; }

    function fmt2(n) { return nf.format(Number(n.toFixed(2))); }

    function refresh() {
        var inputs = document.querySelectorAll('#bet_limits_form .limit-input');
        var changed = false;
        var allValid = true;

        inputs.forEach(function (inp) {
            var val = toNumber(inp.value);
            var orig = toNumber(inp.getAttribute('data-original'));

            if (!isValid(val)) {
                allValid = false;
                inp.classList.add('is-invalid');
            } else {
                inp.classList.remove('is-invalid');
            }

            if (isValid(val) && isValid(orig)) {
                if (Number(val.toFixed(2)) !== Number(orig.toFixed(2))) changed = true;
            } else {
                allValid = false;
            }
        });

        var btn = document.getElementById('btn_save_limits');
        if (btn) btn.disabled = !(changed && allValid);
    }

    function bindFormatOnBlur() {
        document.querySelectorAll('#bet_limits_form .limit-input').forEach(function (inp) {
            inp.addEventListener('blur', function () {
                var v = toNumber(inp.value);
                if (isValid(v)) inp.value = fmtInput(v);
                refresh();
            });
        });
    }

    function fmtInput(n) {
        return Number(n).toFixed(2);
    }

    document.addEventListener('input', function (ev) {
        if (ev.target && ev.target.classList.contains('limit-input')) refresh();
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('#bet_limits_form .limit-input').forEach(function (inp) {
            var v = toNumber(inp.value);
            if (isValid(v)) {
                inp.value = fmtInput(v);
                var orig = toNumber(inp.getAttribute('data-original'));
                if (isValid(orig)) inp.setAttribute('data-original', fmt2(orig));
            }
        });
        bindFormatOnBlur();
        refresh();
    });
})();

