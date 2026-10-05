// Give native form submissions immediate feedback without changing their data.
(() => {
    const desk = document.getElementById('orderTabsContent');
    const feedback = document.getElementById('order-action-feedback');
    if (!desk || !feedback) return;

    let pending = false;
    const originalLabels = new Map();

    desk.addEventListener('submit', event => {
        const form = event.target;
        if (event.defaultPrevented || form.method.toLowerCase() !== 'post') return;
        if (pending) {
            event.preventDefault();
            return;
        }
        const button = event.submitter || form.querySelector('button[type="submit"]');
        if (button?.dataset.confirm && !window.confirm(button.dataset.confirm)) {
            event.preventDefault();
            return;
        }

        pending = true;
        form.setAttribute('aria-busy', 'true');
        const label = button?.dataset.pendingLabel || 'Saving…';
        feedback.textContent = `${label} Please wait for the updated orders.`;
        feedback.hidden = false;
        desk.querySelectorAll('button[type="submit"]').forEach(control => {
            originalLabels.set(control, control.textContent);
            control.disabled = true;
        });
        if (button) button.textContent = label;
        // Keep inputs enabled: disabled fields are omitted from form submissions.
    });

    // Restore controls when the browser returns to this page from its back cache.
    window.addEventListener('pageshow', () => {
        pending = false;
        originalLabels.forEach((label, control) => {
            control.textContent = label;
            control.disabled = false;
        });
        originalLabels.clear();
        desk.querySelectorAll('form[aria-busy]').forEach(form => form.removeAttribute('aria-busy'));
        feedback.hidden = true;
    });
})();
