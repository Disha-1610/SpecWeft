import Resolver from '@forge/resolver';
import api, { invokeRemote, route } from '@forge/api';
import { analyzePullRequest, runMergeCheck, UserError } from './specweft';

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

const resolver = new Resolver();

resolver.define('analyze', async ({ context }) => {
  const ext = context?.extension ?? {};
  try {
    const result = await analyzePullRequest({
      workspaceId: context?.workspaceId,
      repoUuid: ext?.repository?.uuid,
      prId: ext?.pullRequest?.id,
    }, deps);
    return { ok: true, result };
  } catch (e) {
    console.error('specweft analyze failed', e);
    return { ok: false, error: e instanceof UserError ? e.message : 'Unexpected error while analyzing this pull request.' };
  }
});

export const handler = resolver.getDefinitions();
export const mergeCheck = async (event) => runMergeCheck(event, deps);
