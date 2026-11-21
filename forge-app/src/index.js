import Resolver from '@forge/resolver';
import api, { assumeTrustedRoute, invokeRemote, route } from '@forge/api';
import { kvs } from '@forge/kvs';
import {
  analyzePullRequest, applyFeedbackEvent, buildPrComment, normalizeFeedback, normalizeSettings, preIndexWorkspace,
  runMergeCheck, storageKey, syncPrivateRepo, UserError,
} from './specweft';

const REMOTE = 'specweft-backend';

async function ensureOk(res, what) {
  if (!res.ok) throw new UserError(`Bitbucket API returned ${res.status} for ${what}.`);
  return res;
}

// `route` URL-encodes interpolated values (Bitbucket UUIDs contain braces).
const deps = {
  async getRepo(ws, repo) {
    const res = await api.asApp().requestBitbucket(route`/2.0/repositories/${ws}/${repo}`);
    return (await ensureOk(res, 'repository')).json();
  },
  async getDiff(ws, repo, pr) {
    const res = await api.asApp().requestBitbucket(route`/2.0/repositories/${ws}/${repo}/pullrequests/${pr}/diff`);
    return (await ensureOk(res, 'pull request diff')).text();
  },
  async getPullRequest(ws, repo, pr) {
    const res = await api.asApp().requestBitbucket(route`/2.0/repositories/${ws}/${repo}/pullrequests/${pr}`);
    return (await ensureOk(res, 'pull request')).json();
  },
  async listRepos(ws) {
    const res = await api.asApp().requestBitbucket(route`/2.0/repositories/${ws}?pagelen=50&sort=-updated_on`);
    return ((await ensureOk(res, 'repository list')).json()).then((j) => j.values || []);
  },
  // Private repos: read with the app's own read:repository scope; the backend never gets credentials.
  async listFiles(ws, repo, branch) {
    const ref = await ensureOk(await api.asApp().requestBitbucket(route`/2.0/repositories/${ws}/${repo}/refs/branches/${branch}`), 'branch');
    const commit = (await ref.json())?.target?.hash;
    if (!commit) throw new UserError('Could not resolve the main branch commit.');
    const files = [];
    let page = null;
    for (let i = 0; i < 100; i += 1) {
      const res = await api.asApp().requestBitbucket(page
        ? route`/2.0/repositories/${ws}/${repo}/src/${commit}/?max_depth=50&pagelen=100&page=${page}`
        : route`/2.0/repositories/${ws}/${repo}/src/${commit}/?max_depth=50&pagelen=100`);
      const j = await (await ensureOk(res, 'repository file list')).json();
      for (const v of j.values || []) if (v.type === 'commit_file') files.push({ path: v.path, size: v.size });
      page = j.next ? new URL(j.next).searchParams.get('page') : null;
      if (!page) break;
    }
    return { commit, files };
  },
  async getFile(ws, repo, commit, path) {
    const enc = (x) => encodeURIComponent(String(x));
    const p = path.split('/').map(enc).join('/');
    const res = await api.asApp().requestBitbucket(assumeTrustedRoute(`/2.0/repositories/${enc(ws)}/${enc(repo)}/src/${enc(commit)}/${p}`));
    return Buffer.from(await (await ensureOk(res, `file ${path}`)).arrayBuffer()).toString('base64');
  },
  async getSettings(repoUuid) { return (await kvs.get(storageKey('settings', repoUuid))) || null; },
  async getFeedback(repoUuid) { return (await kvs.get(storageKey('feedback', repoUuid))) || null; },
  async backend(path, body) {
    const res = await invokeRemote(REMOTE, {
      path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { detail: text.slice(0, 300) }; }
    if (!res.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      throw new UserError(`SpecWeft backend returned ${res.status}: ${detail}`);
    }
    return data;
  },
};

function prContext(context) {
  const ext = context?.extension ?? {};
  return { workspaceId: context?.workspaceId, repoUuid: ext?.repository?.uuid, prId: ext?.pullRequest?.id };
}

function safe(name, fn) {
  return async (req) => {
    try {
      return { ok: true, ...(await fn(req)) };
    } catch (e) {
      console.error(`specweft ${name} failed`, e);
      return { ok: false, error: e instanceof UserError ? e.message : `Unexpected error (${name}).` };
    }
  };
}

const resolver = new Resolver();

resolver.define('analyze', safe('analyze', async ({ context }) => ({ result: await analyzePullRequest(prContext(context), deps) })));

resolver.define('feedback', safe('feedback', async ({ payload, context }) => {
  const { repoUuid, prId } = prContext(context);
  if (!repoUuid) throw new UserError('Missing repository context.');
  const key = storageKey('feedback', repoUuid);
  const next = applyFeedbackEvent(await kvs.get(key), { kind: payload?.kind, path: payload?.path, prId, undo: Boolean(payload?.undo) });
  await kvs.set(key, next);
  return {};
}));

resolver.define('postComment', safe('postComment', async ({ context }) => {
  const c = prContext(context);
  const raw = await buildPrComment(c, deps);
  const res = await api.asApp().requestBitbucket(
    route`/2.0/repositories/${c.workspaceId}/${c.repoUuid}/pullrequests/${c.prId}/comments`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: { raw } }) },
  );
  await ensureOk(res, 'posting the comment');
  return {};
}));

// ----- repository settings page -----
function settingsRepo(context) {
  const uuid = context?.extension?.repository?.uuid;
  if (!uuid) throw new UserError('Missing repository context.');
  return uuid;
}

resolver.define('getSettings', safe('getSettings', async ({ context }) => {
  const uuid = settingsRepo(context);
  const fb = normalizeFeedback(await kvs.get(storageKey('feedback', uuid)));
  return { settings: normalizeSettings(await kvs.get(storageKey('settings', uuid))), dismissed: fb.notRelevant };
}));

resolver.define('saveSettings', safe('saveSettings', async ({ payload, context }) => {
  const settings = normalizeSettings(payload?.settings);
  await kvs.set(storageKey('settings', settingsRepo(context)), settings);
  return { settings };
}));

resolver.define('clearFeedback', safe('clearFeedback', async ({ context }) => {
  await kvs.delete(storageKey('feedback', settingsRepo(context)));
  return {};
}));

resolver.define('indexNow', safe('indexNow', async ({ context }) => {
  const repoUuid = settingsRepo(context);
  const repo = await deps.getRepo(context?.workspaceId, repoUuid);
  if (repo.is_private) {
    const s = await syncPrivateRepo({ workspaceId: context?.workspaceId, repoUuid }, repo, deps);
    return { job: s.done ? s.job : { status: 'running' }, uploaded: { received: s.received, total: s.total } };
  }
  const r = await deps.backend('/forge/prewarm', { repo_full_name: repo.full_name });
  return { job: r.job };
}));

export const handler = resolver.getDefinitions();
export const mergeCheck = async (event) => runMergeCheck(event, deps);

// avi:forge:installed:app — installation context is ari:cloud:bitbucket::workspace/<uuid>
export const onInstalled = async (event) => {
  const ari = event?.context?.cloudId || event?.installationContext || event?.context?.installContext || '';
  const m = String(ari).match(/workspace\/(.+)$/);
  const ws = m ? (m[1].startsWith('{') ? m[1] : `{${m[1]}}`) : null;
  try {
    const r = await preIndexWorkspace(ws, deps);
    console.log(`specweft pre-index queued ${r.queued} repositories`);
  } catch (e) {
    console.error('specweft pre-index failed', e);
  }
};
