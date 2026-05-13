import { register, init } from './router.js';
import { homeView } from './views/home.js';
import { readerView } from './views/reader.js';
import { sync } from './sync.js';

register('/', homeView);
register('/read/:id', readerView);

async function handleSync() {
  const btn = document.getElementById('sync-btn');
  const status = document.getElementById('sync-status');
  btn.disabled = true;
  status.textContent = 'Syncing...';

  try {
    const result = await sync((loaded, total) => {
      status.textContent = `${loaded}/${total}`;
    });
    if (result.synced) {
      status.textContent = `Synced ${result.count} transcripts`;
    } else {
      status.textContent = 'Up to date';
    }
    setTimeout(() => init(), 500);
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  init();
  document.getElementById('sync-btn').addEventListener('click', handleSync);
});
