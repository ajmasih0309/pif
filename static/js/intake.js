(() => {
    const form = document.getElementById('intake-form');
    if (!form) return;
    const list = document.getElementById('recipient-list');
    const feedback = document.getElementById('intake-feedback');
    const submit = document.getElementById('submit-order');
    const originalLabel = submit.textContent;
    let nextIndex = list.children.length;
    let pending = false;
    let styleTarget = null;
    const updateCount = () => {
        list.querySelectorAll('[data-number]').forEach((el, i) => { el.textContent = i + 1; });
        document.getElementById('bikeCounter').textContent = list.children.length;
        document.getElementById('add-recipient').disabled = list.children.length >= 100;
    };
    const sync = () => {
        const check = form.querySelector('[data-sync-contact]');
        const input = list.querySelector('[name="recipient_name[]"]');
        input.readOnly = check.checked;
        if (check.checked) input.value = document.getElementById('contact_name').value;
    };
    form.querySelector('[data-sync-contact]').addEventListener('change', sync);
    document.getElementById('contact_name').addEventListener('input', sync);
    document.getElementById('add-recipient').addEventListener('click', () => {
        if (pending || list.children.length >= 100) return;
        const html = document.getElementById('recipient-template').innerHTML.replaceAll('__INDEX__', String(nextIndex++));
        list.insertAdjacentHTML('beforeend', html);
        updateCount();
        list.lastElementChild.querySelector('input[name="recipient_name[]"]').focus();
    });
    form.addEventListener('click', event => {
        if (pending) return;
        const remove = event.target.closest('[data-remove-recipient]');
        if (remove) {
            const card = remove.closest('[data-recipient]');
            const previous = card.previousElementSibling;
            card.remove(); updateCount();
            previous?.querySelector('input[name="recipient_name[]"]').focus();
        }
        const copy = event.target.closest('[data-copy-recipient]');
        if (copy) {
            const card = copy.closest('[data-recipient]');
            const previous = card.previousElementSibling;
            if (previous) card.querySelectorAll('input, select, textarea').forEach(input => {
                if (input.name && input.name !== 'recipient_name[]') input.value = previous.querySelector(`[name="${input.name}"]`).value;
            });
        }
        const guide = event.target.closest('[data-style-guide]');
        if (guide) {
            styleTarget = document.getElementById(guide.dataset.styleGuide);
            bootstrap.Modal.getOrCreateInstance(document.getElementById('bikeStyleModal')).show();
        }
    });
    document.querySelectorAll('[data-bike-style]').forEach(button => button.addEventListener('click', () => {
        if (styleTarget) styleTarget.value = button.dataset.bikeStyle;
        bootstrap.Modal.getInstance(document.getElementById('bikeStyleModal')).hide();
        styleTarget?.focus();
    }));
    const partner = document.getElementById('pedal_partner_name');
    const type = document.getElementById('order_type');
    if (partner && type) {
        const requirePartner = () => { partner.required = type.value === 'Pedal Partner'; };
        type.addEventListener('change', requirePartner); requirePartner();
    }
    form.addEventListener('submit', event => {
        if (pending) { event.preventDefault(); return; }
        pending = true;
        form.setAttribute('aria-busy', 'true');
        submit.disabled = true;
        submit.textContent = 'Saving…';
        feedback.textContent = 'Saving your request. Please wait for confirmation.';
        feedback.hidden = false;
        // Leave named fields enabled so the browser includes them in the POST.
    });
    window.addEventListener('pageshow', () => {
        pending = false; submit.disabled = false; submit.textContent = originalLabel;
        form.removeAttribute('aria-busy'); feedback.hidden = true;
    });
    if (form.dataset.staff === 'true') {
        for (const [id, endpoint, target] of [['contact_name', '/api/search_contacts', 'contact-list'], ['pedal_partner_name', '/api/search_partners', 'partner-list']]) {
            const input = document.getElementById(id);
            const options = document.getElementById(target);
            let timer, controller;
            input.addEventListener('input', () => {
                clearTimeout(timer); controller?.abort(); options.replaceChildren();
                const query = input.value.trim();
                if (query.length < 2) return;
                timer = setTimeout(async () => {
                    controller = new AbortController();
                    try {
                        const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, { signal: controller.signal });
                        if (!response.ok) return;
                        const data = await response.json();
                        if (input.value.trim() !== query) return;
                        options.replaceChildren(...data.map(value => { const option = document.createElement('option'); option.value = value; return option; }));
                    } catch (_) { /* Manual entry stays available when suggestions fail. */ }
                }, 300);
            });
        }
    }
    document.getElementById('form-errors')?.focus();
})();
