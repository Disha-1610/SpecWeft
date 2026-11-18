// Core logic shared by the PR panel resolver and the merge check.
// Dependencies are injected so the logic is unit-testable without the Forge runtime:
//   deps.getRepo(workspaceId, repoUuid)        -> { slug, full_name }
//   deps.getDiff(workspaceId, repoUuid, prId)  -> unified diff text
//   deps.backend(path, body)                   -> parsed JSON from the SpecWeft backend (throws on non-2xx)

export const MAX_DIFF_CHARS = 4_500_000; // backend accepts 5 MB; keep a margin

export class UserError extends Error {}

async function buildRequest(workspaceId, repoUuid, prId, deps) {
  if (!workspaceId || !repoUuid || !prId) {
    throw new UserError('Missing pull request context (workspace, repository or PR id).');
  }
  const [repo, diff] = await Promise.all([
    deps.getRepo(workspaceId, repoUuid),
    deps.getDiff(workspaceId, repoUuid, prId),
  ]);
  if (diff.length > MAX_DIFF_CHARS) {
    throw new UserError('This pull request diff is too large for SpecWeft to analyze.');
  }
  return { repo_slug: repo.slug, repo_full_name: repo.full_name, pr_id: Number(prId), diff };
}

/** PR panel: fetch repo + diff from Bitbucket, ask the backend for ranked, evidence-backed recommendations. */
export async function analyzePullRequest({ workspaceId, repoUuid, prId }, deps) {
  const body = await buildRequest(workspaceId, repoUuid, prId, deps);
  return deps.backend('/forge/analyze-pr', body);
}

/** Merge check: returns Bitbucket's MergeCheckResponse { success, message }. Never fails because SpecWeft failed. */
export async function runMergeCheck(event, deps) {
  try {
    const body = await buildRequest(event?.workspace?.uuid, event?.repository?.uuid, event?.pullrequest?.id, deps);
    const res = await deps.backend('/forge/merge-check', body);
    return { success: Boolean(res.success), message: String(res.message ?? '') };
  } catch (e) {
    return { success: true, message: `SpecWeft check skipped: ${e.message}` };
  }
}
