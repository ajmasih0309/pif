(() => {
    const form = document.getElementById('intake-form');
    if (!form) return;
    const phone = document.getElementById('contact_phone_number');
    const formatPhone = () => {
        // Keep invalid or overlong input visible rather than silently losing digits.
        if (/[^0-9+().\s-]/.test(phone.value)) return;
        let digits = phone.value.replace(/\D/g, '');
        const hasCountryCode = digits.length === 11 && digits.startsWith('1');
        if (hasCountryCode) digits = digits.slice(1);
        if (digits.length > 10) return;
        const caret = phone.selectionStart;
        const digitOffset = phone.value.slice(0, caret).replace(/\D/g, '').length - (hasCountryCode ? 1 : 0);
        phone.value = digits ? `(${digits.slice(0, 3)}` : '';
        if (digits.length > 3) phone.value += `) ${digits.slice(3, 6)}`;
        if (digits.length > 6) phone.value += `-${digits.slice(6)}`;
        if (document.activeElement === phone && caret !== null) {
            let position = 0, seen = 0;
            while (position < phone.value.length && seen < digitOffset) {
                if (/\d/.test(phone.value[position])) seen++;
                position++;
            }
            phone.setSelectionRange(position, position);
        }
    };
    phone.addEventListener('beforeinput', event => {
        // Backspace/Delete across a separator should remove a digit, not get stuck.
        const start = phone.selectionStart, end = phone.selectionEnd;
        if (start !== end || start === null) return;
        const backwards = event.inputType === 'deleteContentBackward';
        if (!backwards && event.inputType !== 'deleteContentForward') return;
        const adjacent = backwards ? start - 1 : start;
        if (adjacent < 0 || adjacent >= phone.value.length || /\d/.test(phone.value[adjacent])) return;
        let digit = adjacent;
        while (digit >= 0 && digit < phone.value.length && !/\d/.test(phone.value[digit])) digit += backwards ? -1 : 1;
        if (digit < 0 || digit >= phone.value.length) return;
        event.preventDefault();
        phone.setRangeText('', backwards ? digit : start, backwards ? start : digit + 1, 'end');
        formatPhone();
    });
    phone.addEventListener('input', formatPhone);
    phone.addEventListener('blur', formatPhone);
    formatPhone();
    form.addEventListener('input', event => {
        const input = event.target;
        if (input.name !== 'age[]') return;
        const invalid = input.validity.badInput || (input.value !== '' &&
            (!/^[0-9]+$/.test(input.value) || Number(input.value) < 1 || Number(input.value) > 80));
        const message = invalid ? 'Enter a whole-number age from 1 to 80, or leave blank if unknown.' : '';
        input.setCustomValidity(message);
        input.classList.toggle('is-invalid', invalid);
        input.setAttribute('aria-invalid', String(invalid));
        const error = document.getElementById(`${input.id}-live-error`);
        error.textContent = message;
        error.hidden = !invalid;
    });
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
                if (input.name && input.name !== 'recipient_name[]') {
                    input.value = previous.querySelector(`[name="${input.name}"]`).value;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }
        const guide = event.target.closest('[data-style-guide]');
        if (guide) {
            styleTarget = document.getElementById(guide.dataset.styleGuide);
            const choice = styleTarget.name === 'bike_type_first_choice[]' ? 'first' : 'second';
            const recipient = guide.closest('[data-recipient]').querySelector('[data-number]').textContent;
            document.getElementById('bike-style-title').textContent = `Recipient ${recipient}: ${choice} bike choice`;
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
