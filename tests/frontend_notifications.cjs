const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Exercise the actual notification implementation without loading Steam or React.
const source = readFileSync(join(__dirname, '../src/index.tsx'), 'utf8');
const logicSource = source.slice(source.indexOf('class DecktationLogic {'), source.indexOf('// Available button options'));
const compiled = ts.transpileModule(`${logicSource}\nnew DecktationLogic();`, {
  compilerOptions: { target: ts.ScriptTarget.ES2020 },
}).outputText;

function createLogic(store) {
  const warnings = [];
  const logic = vm.runInNewContext(compiled, {
    window: { NotificationStore: store },
    console: { warn: (...args) => warnings.push(args) },
  });
  return { logic, warnings };
}

test('status alerts display without adding malformed notification history', () => {
  const calls = [];
  const tray = [];
  const { logic } = createLogic({
    m_nNextTestNotificationID: 1,
    ProcessNotification(info, notification, type) {
      // Model Steam processing history separately from popup rendering.
      if (info.fnTray) info.fnTray(notification, tray);
      calls.push({ info, notification, type });
    },
  });
  logic.notify('Recording', 1500);
  logic.notify('Sending in 3s', 3500, 'hello');
  assert.equal(tray.length, 0);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].info.showToast, true);
  assert.equal(calls[0].info.toastDurationMS, 1500);
  assert.equal(calls[0].notification.data.body, 'Recording');
  assert.equal(calls[1].notification.data.body, 'hello');
  assert.equal(calls[1].info.toastDurationMS, 3500);
  assert.equal(calls[1].notification.nNotificationID, 2);
});

test('the notification setting suppresses all callers at the shared entry point', () => {
  const { logic } = createLogic({
    ProcessNotification() { assert.fail('disabled alerts must not reach Steam'); },
  });
  logic.showNotifications = false;
  logic.notify('Decktation', 1000, 'Recording for 3 seconds...');
});

test('unavailable or failing notification APIs do not interrupt recording', () => {
  assert.doesNotThrow(() => createLogic(undefined).logic.notify('Recording'));
  const { logic, warnings } = createLogic({
    m_nNextTestNotificationID: 1,
    ProcessNotification() { throw new Error('Steam notification failure'); },
  });
  assert.doesNotThrow(() => logic.notify('Recording'));
  assert.equal(warnings.length, 1);
});
