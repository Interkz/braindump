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

// === SEARCH ===
const SEARCH_INPUT = document.querySelector('.search-input');
const SEARCH_RESULTS = document.querySelector('.search-results');
let cachedDrops = null;

SEARCH_INPUT?.addEventListener('input', (e) => {
  const query = e.target.value.trim();
  if (!query) {
    SEARCH_RESULTS.innerHTML = '';
    return;
  }
  filterLocal(query);
});

SEARCH_INPUT?.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const query = SEARCH_INPUT.value.trim();
    if (!query) return;
    await searchServer(query);
  }
});

async function filterLocal(query) {
  if (!cachedDrops) {
    try {
      const resp = await fetch('/api/drops?limit=200');
      if (resp.ok) {
        const data = await resp.json();
        cachedDrops = data.drops || [];
      }
    } catch { return; }
  }
  const q = query.toLowerCase();
  const matches = cachedDrops.filter(d => d.content.toLowerCase().includes(q));
  renderResults(matches);
}

async function searchServer(query) {
  try {
    const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (resp.ok) {
      const data = await resp.json();
      renderResults(data.drops || []);
    }
  } catch (err) {
    console.error('Search error:', err);
  }
}

function renderResults(drops) {
  if (!SEARCH_RESULTS) return;
  if (drops.length === 0) {
    SEARCH_RESULTS.innerHTML = '<div class="search-no-results">nothing found</div>';
    return;
  }
  SEARCH_RESULTS.innerHTML = drops.map(d => {
    const text = d.content.length > 120 ? d.content.substring(0, 117) + '...' : d.content;
    const date = d.dropped_at ? new Date(d.dropped_at).toLocaleDateString() : '';
    return `<div class="search-result-item">${escapeHtml(text)}<div class="result-meta">${d.content_type} · ${date}</div></div>`;
  }).join('');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function updateCounter() {
  if (!COUNTER) return;
  if (dropCount === 0) {
    COUNTER.textContent = '';
  } else {
    COUNTER.textContent = `${dropCount} in the well`;
  }
}
