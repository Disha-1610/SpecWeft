import React, { useEffect, useState } from 'react';
import ForgeReconciler, {
  Box, Button, Code, DynamicTable, Heading, Inline, Lozenge, SectionMessage, Spinner, Stack, Text,
} from '@forge/react';
import { invoke } from '@forge/bridge';

const LOZENGE = { high: 'removed', medium: 'moved', low: 'default' };
const CHANGE_LABEL = { removed: 'removed', renamed: 'renamed', value_changed: 'value changed', touched: 'touched' };

function loc(l) {
  return `${l.path}${l.line ? `:${l.line}` : ''}`;
}

function Evidence({ rec }) {
  const nav = rec.navigation_evidence;
  return (
    <Stack space="space.050">
      {rec.agreement_evidence.slice(0, 3).map((e) => (
        <Text key={`${e.token}-${e.holder_site.path}`}>
          <Code>{e.token}</Code> {CHANGE_LABEL[e.change_type]}
          {e.renamed_to ? ` → ${e.renamed_to}` : ''} in {loc(e.changed_site)}; still held at {loc(e.holder_site)}
        </Text>
      ))}
      {nav ? (
        <Text>
          Agents: {nav.sessions_with_edge}/{nav.sessions_editing_source} sessions opened this file after editing{' '}
          {rec.changed_file.path} (lift {nav.lift}×{nav.detours ? `, ${nav.detours} after a failing test/build` : ''})
        </Text>
      ) : null}
    </Stack>
  );
}

const POLL_MS = 5000;
const MAX_POLLS = 60; // ~5 minutes

function App() {
  const [state, setState] = useState({ loading: true });
  const [polls, setPolls] = useState(0);

  const load = (quiet = false) => {
    if (!quiet) setState({ loading: true });
    invoke('analyze')
      .then((r) => setState({ loading: false, ...r }))
      .catch((e) => setState({ loading: false, ok: false, error: e.message }));
  };
  useEffect(() => load(), []);

  // first PR in a repo: the backend clones + indexes it in the background; poll until it is ready
  const indexing = state.ok && state.result?.status === 'indexing';
  useEffect(() => {
    if (!indexing || polls >= MAX_POLLS) return undefined;
    const t = setTimeout(() => { setPolls((n) => n + 1); load(true); }, POLL_MS);
    return () => clearTimeout(t);
  }, [indexing, polls]);

  if (state.loading) {
    return <Inline space="space.100" alignBlock="center"><Spinner /><Text>Analyzing this pull request…</Text></Inline>;
  }
  if (!state.ok) {
    return (
      <SectionMessage appearance="error" title="SpecWeft could not analyze this pull request">
        <Text>{state.error}</Text>
        <Button onClick={() => load()}>Retry</Button>
      </SectionMessage>
    );
  }

  const { result } = state;
  if (result.status === 'indexing') {
    return (
      <SectionMessage appearance="information" title="Indexing this repository">
        <Inline space="space.100" alignBlock="center">
          <Spinner />
          <Text>{polls >= MAX_POLLS ? 'Still indexing: this repository is large.' : result.message}</Text>
        </Inline>
        {polls >= MAX_POLLS ? <Button onClick={() => { setPolls(0); load(); }}>Check again</Button> : null}
      </SectionMessage>
    );
  }
  if (result.status === 'failed') {
    return (
      <SectionMessage appearance="warning" title="SpecWeft cannot analyze this repository yet">
        <Text>{result.error}</Text>
      </SectionMessage>
    );
  }
  const recs = result.recommendations;
  const s = result.summary;
  if (!recs.length) {
    return (
      <SectionMessage appearance="success" title="No broken agreements found">
        <Text>None of the {result.changed_files.length} changed file(s) leave a contract dangling in unchanged files.</Text>
      </SectionMessage>
    );
  }

  const head = {
    cells: [
      { key: 'file', content: 'File that may need updating' },
      { key: 'confidence', content: 'Confidence' },
      { key: 'why', content: 'Evidence' },
    ],
  };
  const rows = recs.map((r) => ({
    key: `${r.related_file.repo}:${r.related_file.path}`,
    cells: [
      {
        key: 'file',
        content: (
          <Stack space="space.050">
            <Code>{loc(r.related_file)}</Code>
            {r.cross_repo ? <Lozenge appearance="new">{r.related_file.repo}</Lozenge> : null}
          </Stack>
        ),
      },
      {
        key: 'confidence',
        content: (
          <Stack space="space.050">
            <Lozenge appearance={LOZENGE[r.confidence]}>{r.confidence}</Lozenge>
            <Text size="small">score {r.ranking_score.toFixed(2)}</Text>
          </Stack>
        ),
      },
      { key: 'why', content: <Evidence rec={r} /> },
    ],
  }));

  return (
    <Stack space="space.200">
      {s.high > 0 ? (
        <SectionMessage appearance="warning" title={`${s.high} file(s) very likely need updating`}>
          <Text>Both signals agree: a shared contract changed here, and agents editing these files usually go on to edit them too.</Text>
        </SectionMessage>
      ) : null}
      <Box>
        <Heading size="small">
          {s.total} unchanged file(s) linked to this change ({s.high} high · {s.medium} medium · {s.low} low)
        </Heading>
        <Text size="small">Repository: {result.repo} · Changed: {result.changed_files.join(', ')}</Text>
      </Box>
      <DynamicTable head={head} rows={rows} rowsPerPage={10} />
    </Stack>
  );
}

ForgeReconciler.render(<React.StrictMode><App /></React.StrictMode>);
