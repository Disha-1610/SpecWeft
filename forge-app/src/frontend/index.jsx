import React, { useEffect, useRef, useState } from 'react';
import ForgeReconciler, {
  Box, Button, ButtonGroup, Heading, Inline, Link, Lozenge, ProgressBar, SectionMessage, Spinner, Stack, Text, xcss,
} from '@forge/react';
import { invoke } from '@forge/bridge';

const TIER_LOZENGE = { must: 'removed', likely: 'moved', worth: 'default' };
const card = xcss({
  borderColor: 'color.border', borderWidth: 'border.width', borderStyle: 'solid', borderRadius: 'border.radius',
  padding: 'space.150', backgroundColor: 'elevation.surface',
});

function Site({ label, site }) {
  return (
    <Stack space="space.0">
      <Text size="small" color="color.text.subtlest">{label}</Text>
      {site.url ? <Link href={site.url} openNewTab>{site.label}</Link> : <Text>{site.label}</Text>}
    </Stack>
  );
}

/** Renders `code` spans in the sentence without needing markdown. */
function Sentence({ text }) {
  const parts = text.split('`');
  return <Text>{parts.map((p, i) => (i % 2 ? <Text key={i} as="strong">{p}</Text> : p))}</Text>;
}

function Card({ c, onFeedback, busy }) {
  return (
    <Box xcss={card}>
      <Stack space="space.100">
        <Inline space="space.100" alignBlock="start" spread="space-between">
          <Sentence text={c.text} />
          {c.crossRepo ? <Lozenge appearance="new">{c.repo}</Lozenge> : null}
        </Inline>
        <Inline space="space.400" shouldWrap>
          <Site label="Changed in this PR" site={c.changedSite} />
          <Site label="Still referenced at" site={c.holderSite} />
        </Inline>
        {c.navigation || c.extraEvidence ? (
          <Text size="small" color="color.text.subtle">
            {[c.navigation, c.extraEvidence ? `+${c.extraEvidence} more reference(s)` : null].filter(Boolean).join(' · ')}
          </Text>
        ) : null}
        <Inline space="space.100" alignBlock="center" shouldWrap>
          <ButtonGroup>
            <Button spacing="compact" isDisabled={busy} onClick={() => onFeedback(c, 'not_relevant')}>Not relevant</Button>
            <Button spacing="compact" isDisabled={busy} onClick={() => onFeedback(c, 'already_handled')}>Already handled</Button>
          </ButtonGroup>
          {c.jiraUrl ? <Link href={c.jiraUrl} openNewTab>Create a follow-up Jira issue</Link> : null}
          {c.feedback?.notRelevantVotes ? (
            <Text size="small" color="color.text.subtlest">Marked not relevant {c.feedback.notRelevantVotes}× before (ranked lower)</Text>
          ) : null}
        </Inline>
      </Stack>
    </Box>
  );
}

function Group({ g, open, onToggle, ...rest }) {
  return (
    <Stack space="space.100">
      <Inline space="space.100" alignBlock="center">
        <Lozenge appearance={TIER_LOZENGE[g.key]} isBold={g.key === 'must'}>{g.title}</Lozenge>
        <Text weight="medium">{g.cards.length} file(s)</Text>
        {onToggle ? <Button appearance="subtle" spacing="compact" onClick={onToggle}>{open ? 'Hide' : 'Show'}</Button> : null}
      </Inline>
      <Text size="small" color="color.text.subtle">{g.blurb}</Text>
      {open ? g.cards.map((c) => <Card key={c.id} c={c} {...rest} />) : null}
    </Stack>
  );
}

function Indexing({ result, tries }) {
  const p = result.progress || {};
  const secs = p.elapsed_seconds ?? 0;
  // most repos finish in < 60 s; the bar is an estimate and never reaches 100% on its own
  const est = Math.min(0.95, secs / 75);
  return (
    <SectionMessage appearance="information" title="Indexing this repository">
      <Stack space="space.100">
        <Text>First time on this repository: SpecWeft is reading the code so it knows which files depend on each other.
          This happens once and usually takes under a minute. You can keep this page open; results appear here automatically.</Text>
        <Text size="small">{p.phase || 'Indexing'}… {secs ? `${secs}s elapsed.` : ''}</Text>
        {secs ? <ProgressBar value={est} ariaLabel="Indexing progress" /> : <ProgressBar isIndeterminate ariaLabel="Indexing" />}
        {tries > 24 ? <Text size="small">Large repository: still working, checking every 15 seconds.</Text> : null}
      </Stack>
    </SectionMessage>
  );
}

function summaryLine(groups) {
  const n = (k) => groups.find((g) => g.key === k)?.cards.length || 0;
  const total = groups.reduce((t, g) => t + g.cards.length, 0);
  const must = n('must');
  return must
    ? `${must} file(s) must be updated with this change (${total} to review in total)`
    : `${total} file(s) may need updating with this change`;
}

function App() {
  const [state, setState] = useState({ loading: true });
  const [tries, setTries] = useState(0);
  const [showWorth, setShowWorth] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const last = useRef(null);

  const load = (quiet = false) => {
    if (!quiet) setState({ loading: true });
    return invoke('analyze')
      .then((r) => setState({ loading: false, ...r }))
      .catch((e) => setState({ loading: false, ok: false, error: e.message }));
  };
  useEffect(() => { load(); }, []);

  // first PR in a repo: the backend indexes in the background; keep polling (5 s, then 15 s) until ready
  const indexing = state.ok && state.result?.status === 'indexing';
  useEffect(() => {
    if (!indexing) return undefined;
    const t = setTimeout(() => { setTries((n) => n + 1); load(true); }, tries > 24 ? 15000 : 5000);
    return () => clearTimeout(t);
  }, [indexing, tries]);

  const onFeedback = async (c, kind, undo = false) => {
    setBusy(true);
    const r = await invoke('feedback', { kind, path: c.path, undo }).catch((e) => ({ ok: false, error: e.message }));
    if (!r.ok) setNotice({ appearance: 'error', text: r.error });
    else {
      last.current = undo ? null : { c, kind };
      setNotice(undo ? null : { appearance: 'success', text: kind === 'not_relevant'
        ? `Marked ${c.path} as not relevant. It will rank lower in future PRs in this repository.`
        : `Marked ${c.path} as handled for this PR.` });
      await load(true);
    }
    setBusy(false);
  };

  const postComment = async () => {
    setBusy(true);
    const r = await invoke('postComment').catch((e) => ({ ok: false, error: e.message }));
    setNotice(r.ok ? { appearance: 'success', text: 'Summary posted as a PR comment.' } : { appearance: 'error', text: r.error });
    setBusy(false);
  };

  if (state.loading) {
    return <Inline space="space.100" alignBlock="center"><Spinner /><Text>SpecWeft is checking which other files depend on this change… (the first run can take up to a minute)</Text></Inline>;
  }
  if (!state.ok) {
    return (
      <SectionMessage appearance="error" title="SpecWeft could not analyze this pull request">
        <Stack space="space.100">
          <Text>{state.error}</Text>
          <Text size="small">Most often the free server is waking up after being idle. Wait about 30 seconds and press Retry.</Text>
          <Button onClick={() => load()}>Retry</Button>
        </Stack>
      </SectionMessage>
    );
  }

  const { result } = state;
  if (result.status === 'indexing') return <Indexing result={result} tries={tries} />;
  if (result.status === 'failed') {
    return (
      <SectionMessage appearance="warning" title="SpecWeft cannot analyze this repository yet">
        <Text>{result.error}</Text>
      </SectionMessage>
    );
  }

  const groups = result.groups || [];
  const h = result.hidden || {};
  const hiddenNote = [
    h.handled ? `${h.handled} handled` : null,
    h.ignored ? `${h.ignored} in ignored paths` : null,
    h.threshold ? `${h.threshold} below the confidence threshold` : null,
  ].filter(Boolean).join(' · ');

  return (
    <Stack space="space.200">
      {notice ? (
        <SectionMessage appearance={notice.appearance}>
          <Inline space="space.100" alignBlock="center" shouldWrap>
            <Text>{notice.text}</Text>
            {last.current && notice.appearance === 'success' ? (
              <Button appearance="link" spacing="compact" isDisabled={busy}
                onClick={() => onFeedback(last.current.c, last.current.kind, true)}>Undo</Button>
            ) : null}
          </Inline>
        </SectionMessage>
      ) : null}
      {!groups.length ? (
        <SectionMessage appearance="success" title="Nothing else needs updating">
          <Text>SpecWeft checked the {result.changed_files.length} changed file(s) and found no other file that still depends on what was changed.</Text>
        </SectionMessage>
      ) : (
        <Inline spread="space-between" alignBlock="center" shouldWrap>
          <Stack space="space.050">
            <Heading size="small">{summaryLine(groups)}</Heading>
            <Text size="small" color="color.text.subtle">
              These files were not changed in this PR but still depend on something it changed. Check each one, then mark it
              “Already handled” or “Not relevant” (SpecWeft learns from this).
            </Text>
          </Stack>
          <Button spacing="compact" isDisabled={busy} onClick={postComment}>Post summary as PR comment</Button>
        </Inline>
      )}
      {groups.map((g) => (
        <Group key={g.key} g={g} busy={busy} onFeedback={onFeedback}
          open={g.key !== 'worth' || showWorth} onToggle={g.key === 'worth' ? () => setShowWorth(!showWorth) : null} />
      ))}
      <Text size="small" color="color.text.subtlest">
        Changed: {result.changed_files.join(', ')}{hiddenNote ? ` · Hidden: ${hiddenNote}` : ''}
      </Text>
    </Stack>
  );
}

ForgeReconciler.render(<React.StrictMode><App /></React.StrictMode>);
