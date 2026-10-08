document.addEventListener('DOMContentLoaded', () => {
    const search = document.querySelector('[data-volunteer-search]');
    const choices = document.querySelector('.volunteer-choices');
    const count = document.querySelector('[data-volunteer-count]');
    const updateSelection = () => {
        if (!choices) return;
        const query = (search?.value || '').trim().toLowerCase();
        choices.querySelectorAll('[data-volunteer-choice]').forEach(label => {
            label.hidden = !label.textContent.toLowerCase().includes(query) && !label.querySelector('input').checked;
            label.classList.toggle('d-block', !label.hidden);
        });
        if (count) count.textContent = `${choices.querySelectorAll('input:checked').length} selected`;
    };
    search?.addEventListener('input', updateSelection);
    choices?.addEventListener('change', updateSelection);
    updateSelection();
    document.querySelectorAll('[data-refresh-volunteers]').forEach(button => {
        button.addEventListener('click', async () => {
            button.disabled = true;
            try {
                const response = await fetch('/api/workshop/volunteers', {headers: {'Accept': 'application/json'}});
                if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Refresh failed');
                const people = await response.json();
                const select = document.querySelector('[data-volunteer-select]');
                if (select) {
                    const selected = select.value;
                    select.replaceChildren(new Option('Choose a volunteer', ''));
                    people.forEach(person => select.add(new Option(`${person.volunteer_name} #${person.volunteer_id}`, person.volunteer_id)));
                    select.value = selected;
                    if (count) count.textContent = ' Volunteer list refreshed.';
                }
                if (choices) {
                    const selected = new Set([...choices.querySelectorAll('input:checked')].map(input => input.value));
                    choices.replaceChildren();
                    people.forEach(person => {
                        const label = document.createElement('label');
                        label.className = 'd-block p-1';
                        label.dataset.volunteerChoice = '';
                        const input = document.createElement('input');
                        input.type = 'checkbox'; input.name = 'volunteer_ids'; input.value = person.volunteer_id;
                        input.className = 'form-check-input me-2'; input.checked = selected.has(String(person.volunteer_id));
                        label.append(input, document.createTextNode(`${person.volunteer_name} #${person.volunteer_id}`));
                        choices.append(label);
                    });
                    updateSelection();
                }
            } catch {
                if (count) count.textContent = 'Could not refresh. Check your login and try again; your entries are unchanged.';
            } finally {
                button.disabled = false;
            }
        });
    });
    document.querySelectorAll('[data-workshop-form]').forEach(form => {
        form.addEventListener('submit', event => {
            if (form.dataset.saving) { event.preventDefault(); return; }
            if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) { event.preventDefault(); return; }
            // Disabled submit buttons are omitted from form data. Preserve which
            // action was chosen (for example, Check tag instead of Save).
            if (event.submitter?.name) {
                const action = document.createElement('input');
                action.type = 'hidden'; action.name = event.submitter.name; action.value = event.submitter.value;
                action.dataset.submittedAction = '';
                form.append(action);
            }
            form.dataset.saving = 'true';
            form.querySelectorAll('button:not([type="button"])').forEach(button => { button.disabled = true; });
            const feedback = form.querySelector('[data-save-feedback]');
            if (feedback) feedback.textContent = 'Saving…';
        });
    });
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('[data-workshop-form]').forEach(form => {
            delete form.dataset.saving;
            form.querySelectorAll('[data-submitted-action]').forEach(input => input.remove());
            form.querySelectorAll('button:not([type="button"])').forEach(button => { button.disabled = false; });
            const feedback = form.querySelector('[data-save-feedback]');
            if (feedback) feedback.textContent = '';
        });
    });
});
