// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');

let dropCount = 0;

// Focus input on load
window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
});

// Also focus on any click in the well area
document.querySelector('.well-container')?.addEventListener('click', (e) => {
  if (e.target === INPUT) return;
  INPUT?.focus();
});

// Handle enter key
INPUT?.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const content = INPUT.value.trim();
    if (!content) return;

    // Clear input immediately
    INPUT.value = '';

    // Animate the drop
    animateDrop(content);

    // Send to backend
    await sendDrop(content);
  }
});

// Handle paste — auto-submit after a brief delay
INPUT?.addEventListener('paste', (e) => {
  setTimeout(() => {
    const content = INPUT.value.trim();
    if (content && (content.startsWith('http') || content.length > 100)) {
      INPUT.value = '';
      animateDrop(content.length > 60 ? content.substring(0, 57) + '...' : content);
      sendDrop(content);
    }
  }, 100);
});

function animateDrop(text) {
  if (!VOID) return;

  const item = document.createElement('div');
  item.className = 'falling-item';
  item.textContent = text.length > 80 ? text.substring(0, 77) + '...' : text;
  VOID.appendChild(item);

  // Remove after animation completes
  item.addEventListener('animationend', () => {
    item.remove();
  });

  // Update counter
  dropCount++;
  updateCounter();
}

async function sendDrop(content) {
  try {
    const resp = await fetch('/api/drop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      console.error('Drop failed:', resp.status);
    }
  } catch (err) {
    console.error('Drop error:', err);
  }
}

async function loadDropCount() {
  try {
    const resp = await fetch('/api/drops?count_only=true');
    if (resp.ok) {
      const data = await resp.json();
      dropCount = data.count || 0;
      updateCounter();
    }
  } catch (err) {
    // Silent — counter is non-essential
  }
}

function updateCounter() {
  if (!COUNTER) return;
  if (dropCount === 0) {
    COUNTER.textContent = '';
  } else {
    COUNTER.textContent = `${dropCount} in the well`;
  }
}

// === BULK IMPORT ===
const IMPORT_BTN = document.querySelector('.import-btn');
const IMPORT_OVERLAY = document.querySelector('.import-overlay');
const IMPORT_CLOSE = document.querySelector('.import-close');
const IMPORT_FILE = document.querySelector('.import-file');
const IMPORT_SUBMIT = document.querySelector('.import-submit');
const IMPORT_STATUS = document.querySelector('.import-status');

IMPORT_BTN?.addEventListener('click', () => {
  IMPORT_OVERLAY.hidden = false;
  IMPORT_FILE.value = '';
  IMPORT_SUBMIT.disabled = true;
  IMPORT_STATUS.textContent = '';
});

IMPORT_CLOSE?.addEventListener('click', () => {
  IMPORT_OVERLAY.hidden = true;
});

IMPORT_OVERLAY?.addEventListener('click', (e) => {
  if (e.target === IMPORT_OVERLAY) IMPORT_OVERLAY.hidden = true;
});

IMPORT_FILE?.addEventListener('change', () => {
  const file = IMPORT_FILE.files[0];
  if (!file) {
    IMPORT_SUBMIT.disabled = true;
    IMPORT_STATUS.textContent = '';
    return;
  }
  IMPORT_STATUS.textContent = file.name;
  IMPORT_SUBMIT.disabled = false;
});

IMPORT_SUBMIT?.addEventListener('click', async () => {
  const file = IMPORT_FILE.files[0];
  if (!file) return;

  IMPORT_SUBMIT.disabled = true;
  IMPORT_STATUS.textContent = 'importing...';

  try {
    const text = await file.text();
    let drops;

    if (file.name.endsWith('.json')) {
      const data = JSON.parse(text);
      drops = Array.isArray(data.drops) ? data.drops : Array.isArray(data) ? data.map(d => typeof d === 'string' ? { content: d } : d) : [];
    } else {
      drops = text.split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(content => ({ content }));
    }

    if (drops.length === 0) {
      IMPORT_STATUS.textContent = 'no drops found in file';
      IMPORT_SUBMIT.disabled = false;
      return;
    }

    const resp = await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drops }),
    });

    if (resp.ok) {
      const result = await resp.json();
      IMPORT_STATUS.textContent = `${result.imported} drops imported`;
      dropCount += result.imported;
      updateCounter();
      setTimeout(() => { IMPORT_OVERLAY.hidden = true; }, 1500);
    } else {
      const err = await resp.json().catch(() => ({}));
      IMPORT_STATUS.textContent = err.error || 'import failed';
      IMPORT_SUBMIT.disabled = false;
    }
  } catch (err) {
    IMPORT_STATUS.textContent = 'error reading file';
    IMPORT_SUBMIT.disabled = false;
  }
});
