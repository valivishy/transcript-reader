import { getState, setState, saveTranscript, clearTranscripts } from './db.js';

const GITHUB_USER = 'valivishy';
const GITHUB_REPO = 'transcript-reader';
const BRANCH = 'main';

const API_BASE = `https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}`;
const RAW_BASE = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${BRANCH}`;

async function getRemoteHead() {
  const response = await fetch(`${API_BASE}/commits/${BRANCH}`, {
    headers: { 'Accept': 'application/vnd.github.v3+json' },
  });
  if (!response.ok) throw new Error(`GitHub API error: ${response.status}`);
  const data = await response.json();
  return data.sha;
}

async function fetchManifest() {
  const response = await fetch(`${RAW_BASE}/manifest.json`);
  if (!response.ok) throw new Error(`Failed to fetch manifest: ${response.status}`);
  return response.json();
}

async function fetchTranscript(path) {
  const response = await fetch(`${RAW_BASE}/${path}`);
  if (!response.ok) throw new Error(`Failed to fetch transcript: ${path}`);
  return response.json();
}

async function sync(onProgress) {
  const localSha = await getState('last_sha');
  const remoteSha = await getRemoteHead();

  if (localSha === remoteSha) {
    return { synced: false, reason: 'up-to-date' };
  }

  const manifest = await fetchManifest();
  const total = manifest.videos.length;
  let loaded = 0;

  await clearTranscripts();

  for (const entry of manifest.videos) {
    const transcript = await fetchTranscript(entry.path);
    await saveTranscript(transcript);
    loaded++;
    if (onProgress) onProgress(loaded, total);
  }

  await setState('last_sha', remoteSha);
  await setState('manifest', manifest);

  return { synced: true, count: loaded };
}

async function getManifest() {
  return getState('manifest');
}

export { sync, getManifest, getRemoteHead, fetchManifest, fetchTranscript };
