import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import handler from '../api/assistant.js';

const originalFetch = globalThis.fetch;
const originalKey = process.env.OPENAI_API_KEY;
const originalWorkerKey = process.env.WATCHDOG_WORKER_API_KEY;

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalKey === undefined) delete process.env.OPENAI_API_KEY;
  else process.env.OPENAI_API_KEY = originalKey;
  if (originalWorkerKey === undefined) delete process.env.WATCHDOG_WORKER_API_KEY;
  else process.env.WATCHDOG_WORKER_API_KEY = originalWorkerKey;
});

function response() {
  return {
    setHeader() {},
    status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; },
  };
}

test('reports a missing server-side OpenAI key without making a request', async () => {
  delete process.env.OPENAI_API_KEY;
  globalThis.fetch = () => { throw new Error('Unexpected request'); };
  const res = response();
  await handler({ method: 'POST', body: { message: 'hello' } }, res);
  assert.equal(res.code, 503);
  assert.match(res.body.detail, /OPENAI_API_KEY/);
});

test('continues tool calls statelessly when response storage is disabled', async () => {
  process.env.OPENAI_API_KEY = 'test-key';
  process.env.WATCHDOG_WORKER_API_KEY = 'test-worker-key';
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    if (requests.length === 1) return {
      ok: true,
      json: async () => ({
        output: [
          { type: 'reasoning', id: 'reasoning_1', encrypted_content: 'encrypted-reasoning' },
          { type: 'function_call', id: 'call_1', call_id: 'call_1', name: 'triage_text', arguments: '{"text":"sample"}' },
        ],
      }),
    };
    if (requests.length === 2) return {
      ok: true,
      text: async () => JSON.stringify({ indicators: [] }),
    };
    return {
      ok: true,
      json: async () => ({ output: [{ type: 'message', content: [{ type: 'output_text', text: 'Done.' }] }] }),
    };
  };

  const res = response();
  await handler({ method: 'POST', body: { message: 'Triage this text' } }, res);
  assert.equal(res.code, 200);
  assert.equal(res.body.reply, 'Done.');
  assert.equal(requests.length, 3);
  assert.equal(requests[1].url, 'https://gpt6watchdog-2.onrender.com/v1/triage/text');
  const first = JSON.parse(requests[0].options.body);
  const follow = JSON.parse(requests[2].options.body);
  assert.equal(first.store, false);
  assert.deepEqual(first.include, ['reasoning.encrypted_content']);
  assert.equal(follow.store, false);
  assert.equal(follow.previous_response_id, undefined);
  assert.deepEqual(follow.input.map(item => item.type || item.role), ['user', 'reasoning', 'function_call', 'function_call_output']);
  assert.equal(follow.input[3].call_id, 'call_1');
});
