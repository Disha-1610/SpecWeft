import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analyzePullRequest, runMergeCheck, MAX_DIFF_CHARS } from '../src/specweft.js';

const fake = (over = {}) => ({
  calls: [],
  async getRepo(ws, repo) { this.calls.push(['repo', ws, repo]); return { slug: 'orders', full_name: 'acme/orders' }; },
  async getDiff() { return 'diff --git a/x b/x\n'; },
  async backend(path, body) { this.calls.push([path, body]); return { success: false, message: 'm', recommendations: [] }; },
  ...over,
});

test('analyze sends repo identity + diff to backend', async () => {
  const d = fake();
  await analyzePullRequest({ workspaceId: '{ws}', repoUuid: '{r}', prId: 7 }, d);
  assert.deepEqual(d.calls.at(-1), ['/forge/analyze-pr', { repo_slug: 'orders', repo_full_name: 'acme/orders', pr_id: 7, diff: 'diff --git a/x b/x\n' }]);
});

test('analyze rejects missing context and huge diffs', async () => {
  await assert.rejects(analyzePullRequest({ workspaceId: 'w', repoUuid: null, prId: 1 }, fake()), /Missing/);
  const d = fake({ async getDiff() { return 'x'.repeat(MAX_DIFF_CHARS + 1); } });
  await assert.rejects(analyzePullRequest({ workspaceId: 'w', repoUuid: 'r', prId: 1 }, d), /too large/);
});

test('merge check passes through backend verdict', async () => {
  const r = await runMergeCheck({ workspace: { uuid: 'w' }, repository: { uuid: 'r' }, pullrequest: { id: 3 } }, fake());
  assert.deepEqual(r, { success: false, message: 'm' });
});

test('merge check never blocks when SpecWeft fails', async () => {
  const d = fake({ async backend() { throw new Error('down'); } });
  const r = await runMergeCheck({ workspace: { uuid: 'w' }, repository: { uuid: 'r' }, pullrequest: { id: 3 } }, d);
  assert.equal(r.success, true);
  assert.match(r.message, /skipped: down/);
});
