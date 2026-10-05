const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function page() {
    const listeners = {};
    const pickup = { textContent: 'Save pickup', disabled: false, dataset: {} };
    const cancel = { textContent: 'Cancel', disabled: false,
        dataset: { confirm: 'Cancel this order?', pendingLabel: 'Cancelling…' } };
    const fields = { date_picked_up: '2026-09-28', bike_tag: '81234', return_page: '2' };
    const form = {
        method: 'post', fields, busy: false,
        setAttribute() { this.busy = true; },
        removeAttribute() { this.busy = false; },
        querySelector() { return pickup; },
    };
    const feedback = { hidden: true, textContent: '' };
    const desk = {
        addEventListener(name, handler) { listeners[name] = handler; },
        querySelectorAll(selector) { return selector.startsWith('button') ? [pickup, cancel] : [form]; },
    };
    const window = {
        accepted: true, confirmations: 0,
        confirm() { this.confirmations++; return this.accepted; },
        addEventListener(name, handler) { listeners[name] = handler; },
    };
    const document = { getElementById(id) { return id === 'orderTabsContent' ? desk : feedback; } };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/order_actions.js'), 'utf8'), { document, window });
    function submit(button) {
        const event = { target: form, submitter: button, defaultPrevented: false,
            preventDefault() { this.defaultPrevented = true; } };
        listeners.submit(event);
        return event;
    }
    return { submit, pickup, cancel, form, feedback, window, listeners, fields };
}

test('submission gives immediate feedback, preserves form values and blocks a second action', () => {
    const p = page();
    assert.equal(p.submit(p.pickup).defaultPrevented, false);
    assert.equal(p.pickup.textContent, 'Saving…');
    assert.equal(p.feedback.hidden, false);
    assert.equal(p.form.busy, true);
    assert.equal(p.pickup.disabled, true);
    assert.equal(p.cancel.disabled, true);
    assert.deepEqual(p.form.fields, { date_picked_up: '2026-09-28', bike_tag: '81234', return_page: '2' });
    assert.equal(p.submit(p.cancel).defaultPrevented, true);
    assert.equal(p.window.confirmations, 0);
});

test('declining confirmation leaves the form usable; approving gives cancellation feedback', () => {
    const p = page();
    p.window.accepted = false;
    assert.equal(p.submit(p.cancel).defaultPrevented, true);
    assert.equal(p.cancel.disabled, false);
    assert.equal(p.feedback.hidden, true);
    p.window.accepted = true;
    assert.equal(p.submit(p.cancel).defaultPrevented, false);
    assert.equal(p.cancel.textContent, 'Cancelling…');
    assert.equal(p.window.confirmations, 2);
});

test('back navigation restores enabled controls and allows another submission', () => {
    const p = page();
    p.submit(p.pickup);
    p.listeners.pageshow();
    assert.equal(p.pickup.disabled, false);
    assert.equal(p.cancel.disabled, false);
    assert.equal(p.pickup.textContent, 'Save pickup');
    assert.equal(p.feedback.hidden, true);
    assert.equal(p.form.busy, false);
    assert.equal(p.submit(p.pickup).defaultPrevented, false);
});
