// Keep long orders manageable, including browsers without details[name].
document.querySelectorAll('[data-order-cards]').forEach(list => {
    list.querySelectorAll('.desk-order, .desk-bike').forEach(details => {
        details.addEventListener('toggle', () => {
            if (!details.open) return;
            for (const sibling of details.parentElement.children) {
                if (sibling !== details && sibling.tagName === 'DETAILS' &&
                    sibling.getAttribute('name') === details.getAttribute('name')) {
                    sibling.open = false;
                }
            }
        });
    });
});
