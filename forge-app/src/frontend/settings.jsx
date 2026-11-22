import React, { useEffect, useState } from 'react';
import ForgeReconciler, {
  Button, Heading, Inline, Label, Link, Lozenge, SectionMessage, Select, Spinner, Stack, Text, TextArea, Textfield, Toggle,
} from '@forge/react';
import { invoke } from '@forge/bridge';

const THRESHOLDS = [
  { label: 'Must update only', value: 'high' },
  { label: 'Must update + Likely', value: 'medium' },
  { label: 'Everything (Worth a look is still collapsed)', value: 'low' },
];

const STATUS_LOZENGE = { done: 'success', queued: 'inprogress', running: 'inprogress', uploading: 'inprogress', failed: 'removed' };

function Intro() {
  const [st, setSt] = useState(null);
  useEffect(() => { invoke('repoStatus').then(setSt).catch(() => setSt({ ok: false })); }, []);
  return (
    <SectionMessage appearance="discovery" title="What is SpecWeft?">
      <Stack space="space.100">
        <Text>
          On every pull request, SpecWeft lists the files the PR did not change but probably should have, for example code still
          using a renamed config key. Open any pull request in this repository and look for the
          “SpecWeft — files this PR may break” panel on its Overview tab.
        </Text>
        {!st ? <Inline space="space.100"><Spinner size="small" /><Text>Checking status…</Text></Inline> : st.ok ? (
          <Inline space="space.200" alignBlock="center" shouldWrap>
            <Inline space="space.050" alignBlock="center">
              <Text>Server:</Text>
              {st.backendOnline ? <Lozenge appearance="success">Online</Lozenge> : <Lozenge appearance="removed">Waking up</Lozenge>}
            </Inline>
            {st.index ? (
              <Inline space="space.050" alignBlock="center">
                <Text>This repository:</Text>
                <Lozenge appearance={STATUS_LOZENGE[st.index.status] || 'default'}>{st.index.label}</Lozenge>
              </Inline>
            ) : null}
            {st.prsUrl ? <Link href={st.prsUrl}>Go to pull requests</Link> : null}
          </Inline>
        ) : null}
        {st?.index?.status === 'none' ? (
          <Text size="small">Not indexed yet: it happens automatically on the first PR, or press “Index repository now” below.</Text>
        ) : null}
      </Stack>
    </SectionMessage>
  );
}

function App() {
  const [s, setS] = useState(null);
  const [dismissed, setDismissed] = useState({});
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    invoke('getSettings').then((r) => {
      if (!r.ok) return setMsg({ appearance: 'error', text: r.error });
      setS({ ...r.settings, ignoredText: r.settings.ignoredPaths.join('\n') });
      setDismissed(r.dismissed || {});
      return null;
    });
  }, []);

  const run = async (name, payload, ok) => {
    setBusy(true);
    const r = await invoke(name, payload).catch((e) => ({ ok: false, error: e.message }));
    setMsg(r.ok ? { appearance: 'success', text: ok(r) } : { appearance: 'error', text: r.error });
    setBusy(false);
    return r;
  };

  if (!s) return msg ? <SectionMessage appearance="error"><Text>{msg.text}</Text></SectionMessage> : <Spinner />;
  const set = (k) => (v) => setS({ ...s, [k]: v });
  const dismissedList = Object.entries(dismissed);

  return (
    <Stack space="space.300">
      <Heading size="medium">SpecWeft</Heading>
      <Intro />
      <Heading size="small">Settings</Heading>
      {msg ? <SectionMessage appearance={msg.appearance}><Text>{msg.text}</Text></SectionMessage> : null}

      <Stack space="space.100">
        <Label labelFor="threshold">Confidence threshold</Label>
        <Select inputId="threshold" options={THRESHOLDS} value={THRESHOLDS.find((o) => o.value === s.threshold)}
          onChange={(o) => set('threshold')(o.value)} />
        <Text size="small">Findings below this level are hidden in the pull request panel and PR comments.</Text>
      </Stack>

      <Stack space="space.100">
        <Label labelFor="ignored">Ignored paths</Label>
        <TextArea id="ignored" value={s.ignoredText} placeholder={'docs/**\n*.md\nvendor/'}
          onChange={(e) => set('ignoredText')(e.target.value)} />
        <Text size="small">One glob per line. <Text as="strong">**</Text> matches any folders; a pattern without a slash also matches file names.</Text>
      </Stack>

      <Inline space="space.100" alignBlock="center">
        <Toggle id="merge" isChecked={s.mergeCheckEnabled} onChange={(e) => set('mergeCheckEnabled')(e.target.checked)} />
        <Label labelFor="merge">Block merges when a file must be updated (merge check)</Label>
      </Inline>

      <Stack space="space.100">
        <Heading size="small">Jira follow-ups (optional)</Heading>
        <Text size="small">Adds a “Create a follow-up Jira issue” link to every finding.</Text>
        <Label labelFor="jira">Jira site</Label>
        <Textfield id="jira" value={s.jiraBaseUrl} placeholder="https://your-team.atlassian.net" onChange={(e) => set('jiraBaseUrl')(e.target.value)} />
        <Inline space="space.200">
          <Stack space="space.050">
            <Label labelFor="pid">Project ID</Label>
            <Textfield id="pid" value={s.jiraProjectId} placeholder="10000" onChange={(e) => set('jiraProjectId')(e.target.value)} />
          </Stack>
          <Stack space="space.050">
            <Label labelFor="itype">Issue type ID</Label>
            <Textfield id="itype" value={s.jiraIssueTypeId} placeholder="10001" onChange={(e) => set('jiraIssueTypeId')(e.target.value)} />
          </Stack>
        </Inline>
      </Stack>

      <Inline space="space.100">
        <Button appearance="primary" isDisabled={busy} onClick={async () => {
          const r = await run('saveSettings', { settings: { ...s, ignoredPaths: s.ignoredText } }, () => 'Settings saved.');
          if (r.ok) setS({ ...r.settings, ignoredText: r.settings.ignoredPaths.join('\n') });
        }}>Save</Button>
        <Button isDisabled={busy} onClick={() => run('indexNow', {}, (r) => (r.uploaded && r.uploaded.received < r.uploaded.total
          ? `Private repository: read ${r.uploaded.received} of ${r.uploaded.total} files. Press again to continue.`
          : r.job?.status === 'done' ? 'Repository is indexed.' : 'Indexing started.'))}>
          Index repository now
        </Button>
      </Inline>

      <Stack space="space.100">
        <Heading size="small">Feedback</Heading>
        {dismissedList.length ? (
          <>
            <Text>Files marked “Not relevant” (ranked lower in every PR):</Text>
            {dismissedList.map(([p, n]) => <Text key={p}>{p} ({n}×)</Text>)}
            <Button isDisabled={busy} onClick={async () => {
              const r = await run('clearFeedback', {}, () => 'Feedback cleared.');
              if (r.ok) setDismissed({});
            }}>Clear all feedback</Button>
          </>
        ) : <Text>No files have been marked “Not relevant” yet.</Text>}
      </Stack>
    </Stack>
  );
}

ForgeReconciler.render(<React.StrictMode><App /></React.StrictMode>);
