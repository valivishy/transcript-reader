import { getManifest } from '../sync.js';

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

async function homeView() {
  const manifest = await getManifest();
  if (!manifest || !manifest.videos || manifest.videos.length === 0) {
    return `
      <div class="empty-state">
        <h2>No transcripts yet</h2>
        <p>Tap sync to fetch transcripts from the repository.</p>
      </div>
    `;
  }

  const grouped = {};
  for (const video of manifest.videos) {
    const slug = video.channel_slug;
    if (!grouped[slug]) grouped[slug] = { name: video.channel, videos: [] };
    grouped[slug].videos.push(video);
  }

  let html = '<div class="channel-list">';
  for (const [slug, channel] of Object.entries(grouped)) {
    html += `<section class="channel-section">`;
    html += `<h2 class="channel-name">${channel.name}</h2>`;
    html += `<ul class="video-list">`;
    for (const video of channel.videos) {
      html += `
        <li class="video-item">
          <a href="#/read/${video.id}" class="video-link">
            <span class="video-title">${video.title}</span>
            <span class="video-meta">${formatDate(video.date)} · ${formatDuration(video.duration)}</span>
          </a>
        </li>
      `;
    }
    html += `</ul></section>`;
  }
  html += '</div>';
  return html;
}

export { homeView, formatDuration, formatDate };
