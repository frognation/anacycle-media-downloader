const urlInput = document.getElementById('url');
const outputInput = document.getElementById('output');
const startBtn = document.getElementById('startBtn');
const chooseBtn = document.getElementById('chooseBtn');
const bar = document.getElementById('bar');
const statusText = document.getElementById('statusText');
const pagesProcessed = document.getElementById('pagesProcessed');
const pagesQueued = document.getElementById('pagesQueued');
const filesDownloaded = document.getElementById('filesDownloaded');
const filesFailed = document.getElementById('filesFailed');

let pollTimer = null;

async function startJob() {
  const url = (urlInput.value || '').trim();
  const outputDir = (outputInput.value || '').trim();

  if (!url) {
    alert('Please enter a URL.');
    return;
  }

  try {
    const res = await fetch('/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, outputDir })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Request failed');
    }
    const jobId = data.jobId;
    statusText.innerText = 'Running...';
    bar.style.width = '5%';
    beginPolling(jobId);
  } catch (e) {
    console.error(e);
    alert('Failed to start job: ' + e.message);
  }
}

function beginPolling(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      const s = await res.json();
      if (!res.ok) throw new Error(s.error || 'Status fetch failed');

      pagesProcessed.innerText = s.pagesProcessed || 0;
      pagesQueued.innerText = s.pagesQueued || 0;
      filesDownloaded.innerText = s.filesDownloaded || 0;
      filesFailed.innerText = s.filesFailed || 0;
      statusText.innerText = s.message || s.status || '';
      const pct = Math.max(0, Math.min(100, s.percent || 0));
      bar.style.width = pct + '%';

      if (s.status === 'completed' || s.status === 'error') {
        clearInterval(pollTimer);
        if (s.status === 'completed') {
          statusText.innerText = 'Completed';
          bar.style.width = '100%';
        } else {
          statusText.innerText = s.message || 'Error occurred';
        }
      }
    } catch (e) {
      console.error(e);
      clearInterval(pollTimer);
      statusText.innerText = 'Status fetch failed';
    }
  }, 1000);
}

startBtn.addEventListener('click', startJob);
chooseBtn.addEventListener('click', chooseFolder);

async function chooseFolder() {
  try {
    const res = await fetch('/choose-dir', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Folder selection failed');
    if (data.cancelled) return; // user cancelled
    if (data.path) {
      outputInput.value = data.path;
    }
  } catch (e) {
    console.error(e);
    alert('Folder selection failed: ' + e.message);
  }
}
