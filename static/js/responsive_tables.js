// Keep the same rows and action forms on every screen; label cells as mobile cards.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.portal-content table').forEach(table => {
        const headers = Array.from(table.tHead?.rows[0]?.cells || [], cell => cell.textContent.trim());
        if (!headers.length) return;
        Array.from(table.tBodies).forEach(body => {
            Array.from(body.rows).forEach(row => {
                if (row.cells.length !== headers.length || Array.from(row.cells).some(cell => cell.colSpan > 1)) return;
                Array.from(row.cells).forEach((cell, index) => { cell.dataset.label = headers[index]; });
            });
        });
        table.classList.add('mobile-cards');
    });
});
