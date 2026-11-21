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
  assert.deepEqual(d.calls.at(-1), ['/forge/analyze-pr', { repo_slug: 'orders', repo_full_name: 'acme/orders', is_private: false, pr_id: 7, diff: 'diff --git a/x b/x\n' }]);
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

import { sentence, prepare, rerank, applyFeedbackEvent, isIgnored, normalizeSettings, fileUrl, jiraUrl, commentMarkdown, storageKey, preIndexWorkspace } from '../src/specweft.js';

const rec = (path, confidence, score, ev = {}) => ({
  changed_file: { repo: 'r', path: 'app/config.py' },
  related_file: { repo: 'r', path, line: 14 },
  reason: 'x', cross_repo: false, confidence, ranking_score: score, navigation_evidence: null,
  agreement_evidence: [{ token: 'postgres_password', change_type: 'removed', changed_site: { repo: 'r', path: 'app/config.py', line: 3 },
    holder_site: { repo: 'r', path, line: 14, text: '      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}' }, ...ev }],
});

test('sentence is one actionable line, token shown as written', () => {
  assert.equal(sentence(rec('compose.yml', 'high', 1)), '`compose.yml:14` still uses `POSTGRES_PASSWORD`, which this PR removed.');
  assert.match(sentence(rec('a.py', 'low', 1, { change_type: 'renamed', renamed_to: 'db_url' })), /renamed to `db_url`/);
});

test('feedback: not relevant demotes across PRs, handled hides on that PR only', () => {
  let fb = applyFeedbackEvent(null, { kind: 'not_relevant', path: 'a', prId: 1 });
  fb = applyFeedbackEvent(fb, { kind: 'not_relevant', path: 'a', prId: 2 });
  fb = applyFeedbackEvent(fb, { kind: 'already_handled', path: 'b', prId: 1 });
  const out = rerank([rec('a', 'high', 1), rec('b', 'medium', 0.5)], fb, 1);
  assert.equal(out.find((r) => r.related_file.path === 'a').confidence, 'medium');
  assert.equal(out.find((r) => r.related_file.path === 'a').ranking_score, 0.25);
  assert.equal(out.find((r) => r.related_file.path === 'b').feedback.handled, true);
  assert.equal(rerank([rec('b', 'medium', 0.5)], fb, 2)[0].feedback.handled, false);
  fb = applyFeedbackEvent(fb, { kind: 'not_relevant', path: 'a', undo: true });
  assert.equal(fb.notRelevant.a, 1);
});

test('prepare groups by tier and applies settings', () => {
  const result = { repo: 'r', pr_id: 1, changed_files: ['app/config.py'],
    recommendations: [rec('compose.yml', 'high', 1), rec('docs/x.md', 'medium', 0.5), rec('z.py', 'low', 0.1)] };
  const p = prepare(result, { ignoredPaths: 'docs/**' }, null, { repoHtml: 'https://bitbucket.org/ws/r', sourceCommit: 'abc', destinationCommit: 'def' });
  assert.deepEqual(p.groups.map((g) => g.key), ['must', 'worth']);
  assert.equal(p.hidden.ignored, 1);
  const c = p.groups[0].cards[0];
  assert.equal(c.holderSite.url, 'https://bitbucket.org/ws/r/src/def/compose.yml#lines-14');
  assert.equal(c.changedSite.url, 'https://bitbucket.org/ws/r/src/abc/app/config.py#lines-3');
  assert.equal(prepare(result, { threshold: 'high' }, null).hidden.threshold, 2);
  assert.match(commentMarkdown(p, result), /\*\*Must update\*\* \(1\)/);
});

test('globs, settings, links, keys', () => {
  assert.ok(isIgnored('docs/a/b.md', ['docs/**']));
  assert.ok(isIgnored('x/y/README.md', ['*.md']));
  assert.ok(isIgnored('vendor/a.js', ['vendor/']));
  assert.ok(!isIgnored('src/a.py', ['docs/**', '*.md']));
  assert.equal(normalizeSettings({ threshold: 'bogus', jiraBaseUrl: 'http://evil', jiraProjectId: 'x' }).threshold, 'low');
  assert.equal(normalizeSettings({ jiraBaseUrl: 'http://evil' }).jiraBaseUrl, '');
  assert.equal(fileUrl(null, 'a', 'b', 1), null);
  assert.equal(jiraUrl(normalizeSettings({}), rec('a', 'high', 1)), null);
  assert.match(jiraUrl(normalizeSettings({ jiraBaseUrl: 'https://t.atlassian.net', jiraProjectId: '1', jiraIssueTypeId: '2' }), rec('a', 'high', 1)),
    /^https:\/\/t\.atlassian\.net\/secure\/CreateIssueDetails!init\.jspa\?pid=1&issuetype=2&summary=/);
  assert.equal(storageKey('feedback', '{ab-12}'), 'feedback:ab-12');
});

test('merge check honours the off switch and dismissed findings', async () => {
  const ev = { workspace: { uuid: 'w' }, repository: { uuid: 'r' }, pullrequest: { id: 3 } };
  const off = await runMergeCheck(ev, fake({ async getSettings() { return { mergeCheckEnabled: false }; } }));
  assert.equal(off.success, true);
  const d = fake({
    async getSettings() { return {}; },
    async getFeedback() { return { handled: { '3|compose.yml': 'x' } }; },
    async backend(path) {
      return path === '/forge/merge-check' ? { success: false, message: 'm' }
        : { status: 'ready', repo: 'r', pr_id: 3, recommendations: [rec('compose.yml', 'high', 1)] };
    },
  });
  assert.equal((await runMergeCheck(ev, d)).success, true);
});

test('pre-index queues only public repositories', async () => {
  const sent = [];
  const r = await preIndexWorkspace('{w}', { async listRepos() { return [{ full_name: 'w/a' }, { full_name: 'w/b', is_private: true }]; },
    async backend(p, b) { sent.push(b.repo_full_name); } });
  assert.deepEqual([r.queued, sent], [1, ['w/a']]);
});
