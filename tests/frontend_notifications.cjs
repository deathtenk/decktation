const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = readFileSync(join(__dirname, '../src/index.tsx'), 'utf8');
const logicSource = source.slice(source.indexOf('class DecktationLogic {'), source.indexOf('// Available button options'));
const compiled = ts.transpileModule(`${logicSource}\nnew DecktationLogic();`, {
  compilerOptions: { target: ts.ScriptTarget.ES2020 },
}).outputText;

function createLogic(toast, globals = {}) {
  const calls = [], handles = [], warnings = [];
  const logic = vm.runInNewContext(compiled, {
    window: new Proxy({}, { get() { assert.fail('notifications must not access Steam internals'); } }),
    toaster: { toast: toast || ((options) => {
      calls.push(options);
      const handle = { dismissed: 0, dismiss() { this.dismissed++; } };
      handles.push(handle);
      return handle;
    }) },
    console: { warn: (...args) => warnings.push(args) },
    ...globals,
  });
  return { logic, calls, handles, warnings };
}
const status = (count, text = '', delay = 3) => ({ success: true, recording_start_count: count, pending_text: text, pending_delay: delay });

test('dictation alerts use the public toaster with bounded, silent history', () => {
  const { logic, calls, handles } = createLogic();
  logic.notify('Decktation', 1500, 'Recording...');
  assert.equal(calls[0].title, 'Decktation');
  assert.equal(calls[0].body, 'Recording...');
  assert.equal(calls[0].duration, 1500);
  assert.equal(calls[0].expiration, 1500);
  assert.equal(calls[0].playSound, false);
  assert.equal(calls[0].showNewIndicator, false);
  logic.notify('Transcribing', 2000);
  assert.equal(handles[0].dismissed, 1);
  assert.equal(calls[1].body, 'Transcribing');
});

test('pending text replaces status and clears through the real handle without a new toast', () => {
  const { logic, calls, handles } = createLogic();
  logic.updateNotificationStatus(status(1));
  logic.updateNotificationStatus(status(1, 'hello'));
  assert.equal(handles[0].dismissed, 1);
  assert.equal(calls[1].title, 'Sending in 3s');
  assert.equal(calls[1].duration, 3500);
  logic.updateNotificationStatus(status(1, 'hello'));
  assert.equal(calls.length, 2);
  logic.updateNotificationStatus(status(1));
  assert.equal(handles[1].dismissed, 1);
  assert.equal(calls.length, 2);
});

test('holding PTT to cancel clears pending without dismissing the new recording status', () => {
  const { logic, handles, calls } = createLogic();
  logic.updateNotificationStatus(status(0, 'cancel this'));
  logic.updateNotificationStatus(status(1));
  assert.equal(handles[0].dismissed, 1);
  assert.equal(handles[1].dismissed, 0);
  assert.equal(calls[1].body, '🎤 Recording...');
});

test('disabling alerts dismisses owned entries and consumes transitions without replay', () => {
  const { logic, handles, calls } = createLogic();
  logic.updateNotificationStatus(status(1));
  logic.showNotifications = false;
  assert.equal(handles[0].dismissed, 1);
  logic.updateNotificationStatus(status(2, 'already pending'));
  logic.notify('Test Recording');
  assert.equal(calls.length, 1);
  logic.showNotifications = true;
  logic.updateNotificationStatus(status(2, 'already pending'));
  assert.equal(calls.length, 1);
});

test('unloading dismisses owned entries and suppresses late async notifications', () => {
  const { logic, handles, calls } = createLogic();
  logic.notify('Recording');
  logic.disposeNotifications();
  logic.disposeNotifications();
  logic.updateNotificationStatus(status(2, 'late result'));
  assert.equal(handles[0].dismissed, 1);
  assert.equal(calls.length, 1);
});

test('missing handles and throwing APIs do not interrupt dictation', () => {
  const missing = createLogic(() => undefined);
  assert.doesNotThrow(() => { missing.logic.notify('Recording'); missing.logic.disposeNotifications(); });
  assert.equal(missing.warnings.length, 1);
  const failing = createLogic(() => { throw new Error('notification API unavailable'); });
  assert.doesNotThrow(() => failing.logic.notify('Recording'));
  assert.equal(failing.warnings.length, 1);
  const brokenDismiss = createLogic(() => ({ dismiss() { throw new Error('dismiss failed'); } }));
  brokenDismiss.logic.notify('Recording');
  assert.doesNotThrow(() => brokenDismiss.logic.disposeNotifications());
  assert.equal(brokenDismiss.warnings.length, 1);
});

test('panel test recording avoids duplicate background alerts and does not send text', async () => {
  const stops = [];
  let fixture;
  fixture = createLogic(undefined, {
    startRecording: async () => { fixture.logic.updateNotificationStatus(status(1)); },
    stopRecording: async (send) => stops.push(send),
    getStatus: async () => status(1),
    setTimeout: (fn) => { fn(); return 1; },
  });
  await fixture.logic.testRecording();
  assert.deepEqual(stops, [false]);
  assert.equal(fixture.calls.length, 2);
  assert.equal(fixture.calls[0].body, 'Recording for 3 seconds...');
  assert.equal(fixture.calls[1].body, 'Transcribing...');
  fixture.logic.updateNotificationStatus(status(1));
  assert.equal(fixture.calls.length, 2);
});
