document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-name-search]');
    if (!form) return;
    const query = form.querySelector('input[type="search"]');
    const options = document.querySelector('[data-name-options]');
    const status = document.querySelector('[data-name-status]');
    let timer, controller, generation = 0;
    const search = async () => {
        const current = ++generation;
        controller?.abort();
        const value = query.value.trim();
        // Keep the selected name while refining a search, including during errors.
        const selected = options.querySelector('input:checked');
        const selectedLabel = selected?.closest('label');
        options.replaceChildren(...(selectedLabel ? [selectedLabel] : []));
        if (value.length < 2) {
            status.textContent = 'Type at least two letters to find your name.';
            return;
        }
        controller = new AbortController();
        status.textContent = 'Finding your name…';
        try {
            const response = await fetch(`${query.dataset.namesUrl}?q=${encodeURIComponent(value)}`, {signal: controller.signal});
            if (!response.ok) throw new Error('Search failed');
            const matches = await response.json();
            if (current !== generation) return;
            for (const person of matches) {
                if (String(person.volunteer_id) === selected?.value) continue;
                const label = document.createElement('label');
                label.className = 'marker-panel d-block mb-2';
                const radio = document.createElement('input');
                radio.type = 'radio'; radio.name = 'volunteer_id'; radio.value = person.volunteer_id;
                radio.required = true; radio.className = 'form-check-input me-2';
                label.append(radio, document.createTextNode(` ${person.volunteer_name} #${person.volunteer_id}`));
                options.append(label);
            }
            status.textContent = matches.length ? 'Select your name. Showing up to 10 matches; type more to narrow it down.' : 'No matching names. Check the spelling or ask staff to add you.';
        } catch (error) {
            if (error.name !== 'AbortError' && current === generation) {
                status.textContent = 'Could not search right now. Check your connection and press Find to try again. Your entry is still here.';
            }
        }
    };
    query.addEventListener('input', () => { clearTimeout(timer); controller?.abort(); generation++; timer = setTimeout(search, 250); });
    form.addEventListener('submit', event => { event.preventDefault(); clearTimeout(timer); search(); });
});

document.addEventListener('DOMContentLoaded', () => {
    const picker = document.querySelector('[data-colour-picker]');
    picker?.addEventListener('change', event => {
        if (event.target.name !== 'colour') return;
        const label = event.target.closest('label').querySelector('[data-colour-label]');
        picker.querySelector('[data-colour-selection]').replaceChildren(label.cloneNode(true));
    });
    // Keep the hours link aligned with an edited QR shop, including back navigation.
    const shop = document.querySelector('[name="shop_name"]');
    const hoursLink = document.querySelector('[data-hours-link]');
    const updateHoursLink = () => {
        if (!shop || !hoursLink) return;
        const url = new URL(hoursLink.href);
        url.searchParams.set('shop', shop.value);
        hoursLink.href = url.href;
    };
    shop?.addEventListener('change', updateHoursLink);
    window.addEventListener('pageshow', updateHoursLink);
    updateHoursLink();
});

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('volunteer-time');
    const panel = document.querySelector('[data-volunteer-impact]');
    if (!form || !panel) return;
    let controller, generation = 0;
    const refresh = async () => {
        const current = ++generation;
        controller?.abort();
        const person = form.querySelector('[name="volunteer_id"]:checked, input[type="hidden"][name="volunteer_id"]');
        panel.hidden = !person;
        panel.replaceChildren();
        if (!person) return;
        panel.textContent = 'Loading your year so far…';
        controller = new AbortController();
        try {
            const response = await fetch(panel.dataset.impactUrl, {
                method: 'POST', signal: controller.signal,
                body: new URLSearchParams({volunteer_id: person.value, form_token: panel.dataset.impactToken})
            });
            if (!response.ok) throw new Error('Summary unavailable');
            const html = await response.text();
            if (current === generation) panel.innerHTML = html; // Escaped aggregate-only server template.
        } catch (error) {
            if (error.name !== 'AbortError' && current === generation) {
                panel.textContent = 'Your summary is unavailable right now. You can still log your time below.';
            }
        }
    };
    form.addEventListener('change', event => { if (event.target.name === 'volunteer_id') refresh(); });
    form.addEventListener('reset', () => queueMicrotask(refresh));
    window.addEventListener('pageshow', event => {
        if (event.persisted || form.querySelector('[name="volunteer_id"]:checked')) refresh();
    });
});
