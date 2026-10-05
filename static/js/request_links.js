(() => {
    const link = document.getElementById('created-link');
    if (link) {
        link.value = new URL(link.value, window.location.origin).href;
        document.getElementById('copy-link').addEventListener('click', async () => {
            const feedback = document.getElementById('copy-feedback');
            try {
                await navigator.clipboard.writeText(link.value);
                feedback.textContent = 'Link copied.';
            } catch (_) {
                link.focus(); link.select();
                feedback.textContent = 'The link is selected. Copy it using your browser or keyboard.';
            }
        });
    }
    const form = document.getElementById('create-link-form');
    const button = form.querySelector('button[type="submit"]');
    const type = document.getElementById('order_type');
    const partner = document.getElementById('pedal_partner_name');
    const requirePartner = () => { partner.required = type.value === 'Pedal Partner'; };
    type.addEventListener('change', requirePartner); requirePartner();
    let pending = false;
    form.addEventListener('submit', event => {
        if (pending) { event.preventDefault(); return; }
        pending = true; button.disabled = true; button.textContent = 'Creating…';
    });
    window.addEventListener('pageshow', () => { pending = false; button.disabled = false; button.textContent = 'Create link'; });
})();
