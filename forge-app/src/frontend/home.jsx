import React, { useEffect, useState } from 'react';
import ForgeReconciler, {
  Box, Button, Heading, Inline, Link, Lozenge, SectionMessage, Spinner, Stack, Text, xcss,
} from '@forge/react';
import { invoke } from '@forge/bridge';

const DEMO_PR = 'https://bitbucket.org/specweft/specweft-demo/pull-requests/2';
const STATUS_LOZENGE = { done: 'success', queued: 'inprogress', running: 'inprogress', uploading: 'inprogress', failed: 'removed' };

const card = xcss({
  borderColor: 'color.border', borderWidth: 'border.width', borderStyle: 'solid', borderRadius: 'border.radius',
  padding: 'space.200', backgroundColor: 'elevation.surface',
});

function Step({ n, title, children }) {
  return (
    <Box xcss={card}>
      <Stack space="space.100">
        <Inline space="space.100" alignBlock="center">
          <Lozenge appearance="new" isBold>{`Step ${n}`}</Lozenge>
          <Text weight="bold">{title}</Text>
        </Inline>
        {children}
      </Stack>
    </Box>
  );
}

function RepoRow({ r }) {
  const st = r.index?.status;
  return (
    <Inline space="space.150" alignBlock="center" spread="space-between" shouldWrap>
      <Inline space="space.100" alignBlock="center">
        {r.url ? <Link href={r.url} openNewTab>{r.name}</Link> : <Text>{r.name}</Text>}
        {r.isPrivate ? <Lozenge>private</Lozenge> : null}
      </Inline>
      <Inline space="space.150" alignBlock="center">
        {r.index ? <Lozenge appearance={STATUS_LOZENGE[st] || 'default'}>{r.index.label}</Lozenge> : null}
        {r.url ? <Link href={`${r.url}/pull-requests/`} openNewTab>Open its pull requests</Link> : null}
      </Inline>
    </Inline>
  );
}

function App() {
  const [data, setData] = useState(null);
  const load = () => {
    setData(null);
    invoke('overview').then(setData).catch((e) => setData({ ok: false, error: e.message }));
  };
  useEffect(load, []);

  return (
    <Stack space="space.300">
      <Stack space="space.100">
        <Heading size="large">Welcome to SpecWeft</Heading>
        <Text>
          When a pull request changes something other files depend on (a config key, a function name, an API field), SpecWeft
          lists the <Text as="strong">files the PR did not touch but probably should have</Text>. It only reads your code and never changes it.
        </Text>
      </Stack>

      <Heading size="medium">How to see it in 3 steps</Heading>
      <Stack space="space.150">
        <Step n={1} title="Open any pull request">
          <Text>Pick a repository below and open one of its pull requests. No PR yet? Edit any file on a new branch and create one.</Text>
        </Step>
        <Step n={2} title="Find the SpecWeft panel">
          <Text>On the PR's Overview tab, scroll to the panel called “SpecWeft — files this PR may break”.</Text>
        </Step>
        <Step n={3} title="Read the results">
          <Text>
            Files are grouped as <Lozenge appearance="removed" isBold>Must update</Lozenge>, <Lozenge appearance="moved">Likely</Lozenge> and{' '}
            <Lozenge>Worth a look</Lozenge>. Each one explains in a sentence why it is linked to the change.
          </Text>
        </Step>
      </Stack>

      <SectionMessage appearance="discovery" title="Just want a quick look?">
        <Text>A ready-made example is on the public demo repository: <Link href={DEMO_PR} openNewTab>open demo pull request</Link>.</Text>
      </SectionMessage>

      <Stack space="space.150">
        <Inline spread="space-between" alignBlock="center">
          <Heading size="medium">Your repositories</Heading>
          <Button spacing="compact" onClick={load}>Refresh</Button>
        </Inline>
        {!data ? (
          <Inline space="space.100" alignBlock="center"><Spinner /><Text>Checking status… (up to 30 s if the server is waking up)</Text></Inline>
        ) : !data.ok ? (
          <SectionMessage appearance="error" title="Could not load status"><Text>{data.error}</Text></SectionMessage>
        ) : (
          <Stack space="space.150">
            <Inline space="space.100" alignBlock="center">
              <Text>SpecWeft server:</Text>
              {data.backendOnline
                ? <Lozenge appearance="success">Online</Lozenge>
                : <Lozenge appearance="removed">Waking up / offline</Lozenge>}
            </Inline>
            {!data.backendOnline ? (
              <Text size="small">The free server sleeps when idle. Wait about 30 seconds and press Refresh.</Text>
            ) : null}
            {data.repos.length ? data.repos.map((r) => <RepoRow key={r.fullName} r={r} />) : (
              <Text>No repositories found in this workspace yet.</Text>
            )}
            <Text size="small" color="color.text.subtlest">
              “Not indexed yet” is fine: a repository is read automatically the first time one of its PRs is opened (about a minute).
              Private repositories are read through this app; your code is never cloned.
            </Text>
          </Stack>
        )}
      </Stack>

      <Text size="small" color="color.text.subtle">
        Settings (confidence level, ignored paths, merge check, Jira) are per repository: Repository settings → SpecWeft.
      </Text>
    </Stack>
  );
}

ForgeReconciler.render(<React.StrictMode><App /></React.StrictMode>);
