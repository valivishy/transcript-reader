const DB_NAME = 'transcript-reader';
const DB_VERSION = 1;
const STORE_TRANSCRIPTS = 'transcripts';
const STORE_STATE = 'state';

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_TRANSCRIPTS)) {
        db.createObjectStore(STORE_TRANSCRIPTS, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(STORE_STATE)) {
        db.createObjectStore(STORE_STATE, { keyPath: 'key' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getState(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_STATE, 'readonly');
    const store = tx.objectStore(STORE_STATE);
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result?.value ?? null);
    request.onerror = () => reject(request.error);
  });
}

async function setState(key, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_STATE, 'readwrite');
    const store = tx.objectStore(STORE_STATE);
    store.put({ key, value });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function saveTranscript(transcript) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TRANSCRIPTS, 'readwrite');
    const store = tx.objectStore(STORE_TRANSCRIPTS);
    store.put(transcript);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getTranscript(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TRANSCRIPTS, 'readonly');
    const store = tx.objectStore(STORE_TRANSCRIPTS);
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result ?? null);
    request.onerror = () => reject(request.error);
  });
}

async function getAllTranscripts() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TRANSCRIPTS, 'readonly');
    const store = tx.objectStore(STORE_TRANSCRIPTS);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function clearTranscripts() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_TRANSCRIPTS, 'readwrite');
    const store = tx.objectStore(STORE_TRANSCRIPTS);
    store.clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export { openDB, getState, setState, saveTranscript, getTranscript, getAllTranscripts, clearTranscripts };
