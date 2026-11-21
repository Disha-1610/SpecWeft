// Core logic shared by the PR panel resolver, the merge check, the settings page and the install trigger.
// Dependencies are injected so the logic is unit-testable without the Forge runtime:
//   deps.getRepo(workspaceId, repoUuid)          -> { slug, full_name, is_private, links }
//   deps.getDiff(workspaceId, repoUuid, prId)    -> unified diff text
//   deps.getPullRequest(workspaceId, repoUuid, prId) -> Bitbucket PR JSON (optional; used for file links)
//   deps.backend(path, body)                     -> parsed JSON from the SpecWeft backend (throws on non-2xx)
//   deps.getSettings(repoUuid) / deps.getFeedback(repoUuid) -> stored objects (optional; defaults used if absent)

export const MAX_DIFF_CHARS = 4_500_000; // backend accepts 5 MB; keep a margin

export class UserError extends Error {}

// ---------- settings ----------

export const TIERS = [
  { key: 'must', confidence: 'high', title: 'Must update', blurb: 'Both signals agree: a shared contract changed and agents editing these files go on to edit them too.' },
  { key: 'likely', confidence: 'medium', title: 'Likely', blurb: 'A contract this PR changed is still referenced here.' },
  { key: 'worth', confidence: 'low', title: 'Worth a look', blurb: 'Weaker links. Hidden by default.' },
];
const RANK = { high: 3, medium: 2, low: 1 };

export const DEFAULT_SETTINGS = {
  threshold: 'low',          // lowest confidence shown: high | medium | low
  ignoredPaths: [],          // glob patterns, e.g. "docs/**", "*.md"
  mergeCheckEnabled: true,
  jiraBaseUrl: '',           // e.g. https://acme.atlassian.net
  jiraProjectId: '',         // numeric project id
  jiraIssueTypeId: '',       // numeric issue type id (e.g. Task)
};

export function normalizeSettings(raw) {
  const s = { ...DEFAULT_SETTINGS, ...(raw || {}) };
  if (!RANK[s.threshold]) s.threshold = DEFAULT_SETTINGS.threshold;
  if (typeof s.ignoredPaths === 'string') s.ignoredPaths = s.ignoredPaths.split(/\r?\n|,/);
  s.ignoredPaths = (Array.isArray(s.ignoredPaths) ? s.ignoredPaths : []).map((p) => String(p).trim()).filter(Boolean).slice(0, 100);
  s.mergeCheckEnabled = s.mergeCheckEnabled !== false;
  s.jiraBaseUrl = String(s.jiraBaseUrl || '').trim().replace(/\/+$/, '');
  if (s.jiraBaseUrl && !/^https:\/\/[^/\s]+$/.test(s.jiraBaseUrl)) s.jiraBaseUrl = '';
  s.jiraProjectId = /^\d+$/.test(String(s.jiraProjectId || '').trim()) ? String(s.jiraProjectId).trim() : '';
  s.jiraIssueTypeId = /^\d+$/.test(String(s.jiraIssueTypeId || '').trim()) ? String(s.jiraIssueTypeId).trim() : '';
  return s;
}

/** Minimal glob: `**` any path, `*` any chars except `/`, `?` one char. Pattern without `/` matches the basename too. */
export function globToRegExp(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i += 1) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') { re += '.*'; i += 1; if (glob[i + 1] === '/') i += 1; } else if (c === '*') re += '[^/]*';
    else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp(`^${re}$`);
}

export function isIgnored(path, patterns) {
  const base = path.split('/').pop();
  return patterns.some((p) => {
    const rx = globToRegExp(p.endsWith('/') ? `${p}**` : p);
    return rx.test(path) || (!p.includes('/') && rx.test(base));
  });
}

// ---------- feedback ----------

export const FEEDBACK_KINDS = ['not_relevant', 'already_handled'];

/** feedback = { notRelevant: { path: count }, handled: { "<prId>|<path>": iso } } */
export function normalizeFeedback(raw) {
  return { notRelevant: { ...(raw?.notRelevant || {}) }, handled: { ...(raw?.handled || {}) } };
}

export function applyFeedbackEvent(feedback, { kind, path, prId, undo = false }) {
  const fb = normalizeFeedback(feedback);
  if (!FEEDBACK_KINDS.includes(kind) || !path) throw new UserError('Invalid feedback.');
  if (kind === 'not_relevant') {
    const n = (fb.notRelevant[path] || 0) + (undo ? -1 : 1);
    if (n > 0) fb.notRelevant[path] = n; else delete fb.notRelevant[path];
  } else {
    const k = `${prId}|${path}`;
    if (undo) delete fb.handled[k]; else fb.handled[k] = new Date().toISOString();
  }
  return fb;
}

/**
 * Feed stored feedback back into ranking. "Not relevant" on this file in any PR of the repo halves its score per vote
 * and drops it one tier from the second vote on. "Already handled" hides the file on this PR only.
 */
export function rerank(recs, feedback, prId) {
  const fb = normalizeFeedback(feedback);
  const out = [];
  for (const r of recs) {
    const path = r.related_file.path;
    const votes = fb.notRelevant[path] || 0;
    const handled = Boolean(fb.handled[`${prId}|${path}`]);
    let confidence = r.confidence;
    if (votes >= 2) confidence = confidence === 'high' ? 'medium' : 'low';
    out.push({ ...r, confidence, original_confidence: r.confidence, ranking_score: r.ranking_score * 0.5 ** votes,
      feedback: { notRelevantVotes: votes, handled } });
  }
  return out.sort((a, b) => RANK[b.confidence] - RANK[a.confidence] || b.ranking_score - a.ranking_score);
}

// ---------- cards ----------

function loc(l) {
  return `${l.path}${l.line ? `:${l.line}` : ''}`;
}

/** One actionable sentence, e.g. "`compose.yml:14` still uses `POSTGRES_PASSWORD`, which this PR removed." */
export function sentence(rec) {
  const e = rec.agreement_evidence?.[0];
  const where = `\`${loc(e?.holder_site || rec.related_file)}\``;
  if (!e) {
    const nav = rec.navigation_evidence;
    if (nav) return `${where} is usually edited next: ${nav.sessions_with_edge} of ${nav.sessions_editing_source} agent sessions that changed \`${rec.changed_file.path}\` went on to change it.`;
    return `${where} may need updating: ${rec.reason}`;
  }
  const tok = `\`${matchCase(e.holder_site?.text || '', e.token)}\``; // show it as written in the file (POSTGRES_PASSWORD)
  switch (e.change_type) {
    case 'removed': return `${where} still uses ${tok}, which this PR removed.`;
    case 'renamed': return `${where} still uses ${tok}, which this PR renamed to \`${e.renamed_to}\`.`;
    case 'value_changed':
      return `${where} still relies on ${tok}, whose value this PR changed${e.old_value != null && e.new_value != null ? ` from \`${e.old_value}\` to \`${e.new_value}\`` : ''}.`;
    default: return `${where} uses ${tok}, which this PR touches. Check it still matches.`;
  }
}

function matchCase(text, token) {
  const i = text.toLowerCase().indexOf(token);
  return i < 0 ? token : text.slice(i, i + token.length);
}

/** Bitbucket "view file at line" URL. */
export function fileUrl(repoHtml, commit, path, line) {
  if (!repoHtml || !commit || !path) return null;
  const p = path.split('/').map(encodeURIComponent).join('/');
  return `${repoHtml.replace(/\/+$/, '')}/src/${encodeURIComponent(commit)}/${p}${line ? `#lines-${line}` : ''}`;
}

export function jiraUrl(settings, rec, prUrl) {
  if (!settings.jiraBaseUrl || !settings.jiraProjectId || !settings.jiraIssueTypeId) return null;
  const q = new URLSearchParams({
    pid: settings.jiraProjectId,
    issuetype: settings.jiraIssueTypeId,
    summary: `Follow up: update ${rec.related_file.path}`.slice(0, 250),
    description: `${sentence(rec)}\n\nFound by SpecWeft${prUrl ? ` on ${prUrl}` : ''}.`,
  });
  return `${settings.jiraBaseUrl}/secure/CreateIssueDetails!init.jspa?${q}`;
}

export function buildCards(recs, { repoName, links, settings, prId }) {
  return recs.map((r) => {
    const e = r.agreement_evidence?.[0];
    const sameRepo = !r.cross_repo && r.related_file.repo === repoName;
    const changed = e?.changed_site || r.changed_file;
    const holder = e?.holder_site || r.related_file;
    return {
      id: `${r.related_file.repo}:${r.related_file.path}`,
      path: r.related_file.path,
      repo: r.related_file.repo,
      crossRepo: Boolean(r.cross_repo),
      confidence: r.confidence,
      tier: TIERS.find((t) => t.confidence === r.confidence).key,
      score: r.ranking_score,
      text: sentence(r),
      changedSite: { label: loc(changed), url: fileUrl(links.repoHtml, links.sourceCommit, changed.path, changed.line) },
      holderSite: { label: loc(holder), url: sameRepo ? fileUrl(links.repoHtml, links.destinationCommit, holder.path, holder.line) : null },
      extraEvidence: Math.max(0, (r.agreement_evidence?.length || 0) - 1),
      navigation: r.navigation_evidence ? `${r.navigation_evidence.sessions_with_edge}/${r.navigation_evidence.sessions_editing_source} agent sessions edited it next (lift ${r.navigation_evidence.lift}×)` : null,
      jiraUrl: jiraUrl(settings, r, links.prHtml),
      feedback: r.feedback,
      prId,
    };
  });
}

/** Settings + feedback applied to backend recommendations. Hidden (handled / below threshold / ignored) are counted. */
export function prepare(result, settings, feedback, links = {}) {
  const s = normalizeSettings(settings);
  const recs = rerank(result.recommendations || [], feedback, result.pr_id);
  const hidden = { handled: 0, ignored: 0, threshold: 0 };
  const visible = recs.filter((r) => {
    if (r.feedback.handled) { hidden.handled += 1; return false; }
    if (isIgnored(r.related_file.path, s.ignoredPaths)) { hidden.ignored += 1; return false; }
    if (RANK[r.confidence] < RANK[s.threshold]) { hidden.threshold += 1; return false; }
    return true;
  });
  const handled = recs.filter((r) => r.feedback.handled);
  const cards = buildCards(visible, { repoName: result.repo, links, settings: s, prId: result.pr_id });
  const groups = TIERS.map((t) => ({ ...t, cards: cards.filter((c) => c.tier === t.key) })).filter((g) => g.cards.length);
  return { groups, hidden, handledCards: buildCards(handled, { repoName: result.repo, links, settings: s, prId: result.pr_id }), visible };
}

export function commentMarkdown(prepared, result) {
  const lines = ['### SpecWeft: unchanged files this PR may break', ''];
  if (!prepared.visible.length) {
    lines.push(`No broken agreements found across ${result.changed_files?.length ?? 0} changed file(s).`);
  }
  for (const g of prepared.groups) {
    lines.push(`**${g.title}** (${g.cards.length})`, '');
    for (const c of g.cards.slice(0, 10)) {
      lines.push(`- ${c.holderSite.url ? c.text.replace(`\`${c.holderSite.label}\``, `[\`${c.holderSite.label}\`](${c.holderSite.url})`) : c.text}`);
    }
    if (g.cards.length > 10) lines.push(`- …and ${g.cards.length - 10} more`);
    lines.push('');
  }
  lines.push('_Posted from the SpecWeft panel. Mark findings "Not relevant" there to tune future results._');
  return lines.join('\n');
}

// ---------- Bitbucket / backend flows ----------

async function buildRequest(workspaceId, repoUuid, prId, deps) {
  if (!workspaceId || !repoUuid || !prId) {
    throw new UserError('Missing pull request context (workspace, repository or PR id).');
  }
  const [repo, diff, pr] = await Promise.all([
    deps.getRepo(workspaceId, repoUuid),
    deps.getDiff(workspaceId, repoUuid, prId),
    deps.getPullRequest ? deps.getPullRequest(workspaceId, repoUuid, prId).catch(() => null) : null,
  ]);
  if (diff.length > MAX_DIFF_CHARS) {
    throw new UserError('This pull request diff is too large for SpecWeft to analyze.');
  }
  const links = {
    repoHtml: repo?.links?.html?.href || null,
    prHtml: pr?.links?.html?.href || null,
    sourceCommit: pr?.source?.commit?.hash || pr?.source?.branch?.name || null,
    destinationCommit: pr?.destination?.commit?.hash || pr?.destination?.branch?.name || null,
  };
  return {
    body: {
      repo_slug: repo.slug,
      repo_full_name: repo.full_name,
      is_private: Boolean(repo.is_private),
      pr_id: Number(prId),
      diff,
    },
    links,
  };
}

async function loadPrefs(repoUuid, deps) {
  const [settings, feedback] = await Promise.all([
    deps.getSettings ? deps.getSettings(repoUuid) : null,
    deps.getFeedback ? deps.getFeedback(repoUuid) : null,
  ]);
  return { settings: normalizeSettings(settings), feedback: normalizeFeedback(feedback) };
}

/** PR panel: fetch repo + diff from Bitbucket, ask the backend for ranked recommendations, apply settings + feedback. */
export async function analyzePullRequest({ workspaceId, repoUuid, prId }, deps) {
  const { body, links } = await buildRequest(workspaceId, repoUuid, prId, deps);
  const [result, prefs] = await Promise.all([deps.backend('/forge/analyze-pr', body), loadPrefs(repoUuid, deps)]);
  if (result.status !== 'ready') return result;
  const p = prepare(result, prefs.settings, prefs.feedback, links);
  return { ...result, groups: p.groups, hidden: p.hidden, handledCards: p.handledCards,
    jiraConfigured: Boolean(jiraUrl(prefs.settings, { related_file: { path: '' }, reason: '' }, null)) };
}

/** Markdown summary for a PR comment, built from the same filtered view the panel shows. */
export async function buildPrComment({ workspaceId, repoUuid, prId }, deps) {
  const { body, links } = await buildRequest(workspaceId, repoUuid, prId, deps);
  const [result, prefs] = await Promise.all([deps.backend('/forge/analyze-pr', body), loadPrefs(repoUuid, deps)]);
  if (result.status !== 'ready') throw new UserError('SpecWeft is still indexing this repository; try again shortly.');
  return commentMarkdown(prepare(result, prefs.settings, prefs.feedback, links), result);
}

/** Merge check: returns Bitbucket's MergeCheckResponse { success, message }. Never fails because SpecWeft failed. */
export async function runMergeCheck(event, deps) {
  try {
    const repoUuid = event?.repository?.uuid;
    const prefs = await loadPrefs(repoUuid, deps);
    if (!prefs.settings.mergeCheckEnabled) return { success: true, message: 'SpecWeft check is turned off in repository settings.' };
    const { body } = await buildRequest(event?.workspace?.uuid, repoUuid, event?.pullrequest?.id, deps);
    const res = await deps.backend('/forge/merge-check', body);
    if (res.success || !deps.getFeedback) return { success: Boolean(res.success), message: String(res.message ?? '') };
    // backend found high-confidence breaks: re-check them against this repo's settings + feedback
    const full = await deps.backend('/forge/analyze-pr', body);
    if (full.status !== 'ready') return { success: true, message: 'SpecWeft: check skipped (not ready).' };
    const must = prepare(full, prefs.settings, prefs.feedback).visible.filter((r) => r.confidence === 'high');
    if (!must.length) return { success: true, message: 'SpecWeft: high-confidence findings were dismissed or ignored for this repository.' };
    return { success: false, message: `SpecWeft: ${must.length} file(s) must be updated: ${must.slice(0, 5).map((r) => r.related_file.path).join(', ')}` };
  } catch (e) {
    return { success: true, message: `SpecWeft check skipped: ${e.message}` };
  }
}

/** Install trigger: ask the backend to index every public repository in the workspace so the first PR is instant. */
export async function preIndexWorkspace(workspaceId, deps, max = 25) {
  if (!workspaceId) return { queued: 0 };
  const repos = (await deps.listRepos(workspaceId)).filter((r) => !r.is_private).slice(0, max);
  let queued = 0;
  for (const r of repos) {
    try { await deps.backend('/forge/prewarm', { repo_full_name: r.full_name }); queued += 1; } catch (e) { /* keep going */ }
  }
  return { queued };
}

/** KVS keys allow only [a-zA-Z0-9:._\s-#]; Bitbucket UUIDs have braces. */
export function storageKey(kind, repoUuid) {
  return `${kind}:${String(repoUuid || '').replace(/[^a-zA-Z0-9:._-]/g, '')}`;
}
