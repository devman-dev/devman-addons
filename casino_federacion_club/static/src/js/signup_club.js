
document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('club_combobox');
    var hidden = document.getElementById('club_id_hidden');
    var dropdown = document.querySelector('.club-dd-list');

    if (!input || !dropdown) return;

    // Show dropdown on focus
    input.addEventListener('focus', function() {
        dropdown.style.display = '';
        filterClubs();
    });

    // Filter on input
    input.addEventListener('input', filterClubs);

    // Hide on blur (delayed for click to register)
    input.addEventListener('blur', function() {
        setTimeout(function() { dropdown.style.display = 'none'; }, 200);
    });

    // Click on item
    dropdown.addEventListener('click', function(e) {
        var item = e.target.closest('.club-dd-item');
        if (!item) return;
        hidden.value = item.dataset.id;
        input.value = item.dataset.name;
        // Highlight selected
        document.querySelectorAll('.club-dd-item').forEach(function(el) { el.classList.remove('selected'); });
        item.classList.add('selected');
        dropdown.style.display = 'none';
    });

    function filterClubs() {
        var v = input.value.toLowerCase();
        var any = false;
        document.querySelectorAll('.club-dd-item').forEach(function(el) {
            var match = !v || el.dataset.name.toLowerCase().indexOf(v) >= 0;
            el.style.display = match ? 'flex' : 'none';
            if (match) any = true;
        });
        document.querySelectorAll('.club-dd-group').forEach(function(g) {
            var has = g.querySelector('.club-dd-item:not([style*="display: none"])');
            g.style.display = has ? 'block' : 'none';
        });
        if (!v) {
            document.querySelectorAll('.club-dd-group, .club-dd-item').forEach(function(e) { e.style.display = ''; });
        }
        if (dropdown) dropdown.style.display = '';
    }
});
