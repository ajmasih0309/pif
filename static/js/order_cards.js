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

// Prevent dropdown clicks from bubbling to <summary> and toggling the card
document.querySelectorAll('.desk-actions-wrap, .desk-actions-dropdown').forEach(wrap => {
    wrap.addEventListener('click', e => {
        e.stopPropagation();
    });
});

// Manage stacking context so active dropdown is never hidden behind neighboring cards
document.addEventListener('show.bs.dropdown', e => {
    const card = e.target.closest('.desk-order');
    if (card) card.style.zIndex = '100';
});
document.addEventListener('hide.bs.dropdown', e => {
    const card = e.target.closest('.desk-order');
    if (card) card.style.zIndex = '';
});
