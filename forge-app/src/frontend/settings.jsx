import React, { useEffect, useState } from 'react';
import ForgeReconciler, {
  Button, Heading, Inline, Label, SectionMessage, Select, Spinner, Stack, Text, TextArea, Textfield, Toggle,
} from '@forge/react';
import { invoke } from '@forge/bridge';

const THRESHOLDS = [
  { label: 'Must update only', value: 'high' },
  { label: 'Must update + Likely', value: 'medium' },
  { label: 'Everything (Worth a look is still collapsed)', value: 'low' },
];

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
        <Button isDisabled={busy} onClick={() => run('indexNow', {}, (r) => (r.job?.status === 'done' ? 'Repository is already indexed.' : 'Indexing started.'))}>
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
