import { getTranscript } from '../db.js';
import { getState, setState } from '../db.js';

function formatTimestamp(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

async function readerView(params) {
  const { id } = params;
  const transcript = await getTranscript(id);

  if (!transcript) {
    return '<p>Transcript not found. Try syncing.</p>';
  }

  let html = `
    <article class="reader">
      <header class="reader-header">
        <a href="#/" class="back-link">&larr; Back</a>
        <h1 class="reader-title">${transcript.title}</h1>
        <p class="reader-meta">${transcript.channel} · ${transcript.date}</p>
      </header>
  `;

  if (transcript.chapters && transcript.chapters.length > 0) {
    html += '<nav class="chapter-nav"><h3>Chapters</h3><ul>';
    for (const ch of transcript.chapters) {
      html += `<li><a href="#chapter-${ch.time}" class="chapter-link">${formatTimestamp(ch.time)} ${ch.title}</a></li>`;
    }
    html += '</ul></nav>';
  }

  html += '<div class="transcript-content">';

  if (!transcript.has_captions || transcript.segments.length === 0) {
    html += '<p class="no-captions">No captions available for this video.</p>';
  } else {
    let chapterIndex = 0;
    for (const segment of transcript.segments) {
      if (transcript.chapters && chapterIndex < transcript.chapters.length) {
        const nextChapter = transcript.chapters[chapterIndex];
        if (segment.time >= nextChapter.time) {
          html += `<h2 class="chapter-heading" id="chapter-${nextChapter.time}">${nextChapter.title}</h2>`;
          chapterIndex++;
        }
      }
      html += `<span class="segment" data-time="${segment.time}">${segment.text} </span>`;
    }
  }

  html += '</div></article>';

  setTimeout(() => initProgressTracking(id), 0);

  return html;
}

async function initProgressTracking(videoId) {
  const progressKey = `progress_${videoId}`;
  const saved = await getState(progressKey);
  if (saved) {
    const el = document.querySelector(`.transcript-content`);
    if (el) el.scrollTop = saved;
  }

  const content = document.querySelector('.transcript-content');
  if (!content) return;

  let debounce = null;
  content.addEventListener('scroll', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      setState(progressKey, content.scrollTop);
    }, 500);
  });
}

export { readerView, formatTimestamp, initProgressTracking };
