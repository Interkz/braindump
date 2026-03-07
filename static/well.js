// Braindump — The Well
// Handles input, drop animation, keyboard navigation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const DROPS_LIST = document.querySelector('.recent-drops');

let dropCount = 0;
let recentDrops = [];
let selectedIndex = -1;
let activeZone = 'input'; // 'input' | 'drops' | 'nav'

// --- Init ---

window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
  loadRecentDrops();
});

// Focus input on click in well area
document.querySelector('.well-container')?.addEventListener('click', (e) => {
  if (e.target === INPUT || e.target.closest('.recent-drops')) return;
  INPUT?.focus();
  setActiveZone('input');
});

// --- Input handling ---

INPUT?.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const content = INPUT.value.trim();
    if (!content) return;
    INPUT.value = '';
    animateDrop(content);
    await sendDrop(content);
    loadRecentDrops();
  }

  // Arrow down from input → enter drops list (j not used here since user is typing)
  if (e.key === 'ArrowDown') {
    if (recentDrops.length > 0) {
      e.preventDefault();
      setActiveZone('drops');
      selectDrop(0);
    }
  }
});

INPUT?.addEventListener('focus', () => {
  setActiveZone('input');
  clearSelection();
});

// --- Paste auto-submit ---

INPUT?.addEventListener('paste', (e) => {
  setTimeout(() => {
    const content = INPUT.value.trim();
    if (content && (content.startsWith('http') || content.length > 100)) {
      INPUT.value = '';
      animateDrop(content.length > 60 ? content.substring(0, 57) + '...' : content);
      sendDrop(content).then(() => loadRecentDrops());
    }
  }, 100);
});

// --- Global keyboard handler ---

document.addEventListener('keydown', (e) => {
  // Tab zone cycling
  if (e.key === 'Tab') {
    e.preventDefault();
    cycleZone(e.shiftKey ? -1 : 1);
    return;
  }

  // Only handle nav keys when drops zone is active
  if (activeZone !== 'drops') return;

  const items = DROPS_LIST?.querySelectorAll('.drop-item');
  if (!items || items.length === 0) return;

  switch (e.key) {
    case 'ArrowDown':
    case 'j':
      e.preventDefault();
      selectDrop(Math.min(selectedIndex + 1, items.length - 1));
      break;

    case 'ArrowUp':
    case 'k':
      e.preventDefault();
      if (selectedIndex <= 0) {
        // Go back to input
        setActiveZone('input');
        INPUT?.focus();
        clearSelection();
      } else {
        selectDrop(selectedIndex - 1);
      }
      break;

    case 'Enter':
      e.preventDefault();
      activateSelectedDrop();
      break;

    case 'Escape':
      e.preventDefault();
      setActiveZone('input');
      INPUT?.focus();
      clearSelection();
      break;
  }
});

// --- Zone management ---

const ZONES = ['input', 'drops', 'nav'];

function cycleZone(direction) {
  const currentIdx = ZONES.indexOf(activeZone);
  const nextIdx = (currentIdx + direction + ZONES.length) % ZONES.length;
  const nextZone = ZONES[nextIdx];

  // Skip drops zone if empty
  if (nextZone === 'drops' && recentDrops.length === 0) {
    const skipIdx = (nextIdx + direction + ZONES.length) % ZONES.length;
    setActiveZone(ZONES[skipIdx]);
    focusZone(ZONES[skipIdx]);
    return;
  }

  setActiveZone(nextZone);
  focusZone(nextZone);
}

function focusZone(zone) {
  if (zone === 'input') {
    INPUT?.focus();
    clearSelection();
  } else if (zone === 'drops') {
    selectDrop(selectedIndex >= 0 ? selectedIndex : 0);
  } else if (zone === 'nav') {
    const navLink = document.querySelector('.nav-link');
    navLink?.focus();
    clearSelection();
  }
}

function setActiveZone(zone) {
  activeZone = zone;
  // Update visual indicators
  document.querySelectorAll('[data-nav-zone]').forEach((el) => {
    el.classList.toggle('nav-zone-active', el.dataset.navZone === zone);
  });
}

// --- Drop selection ---

function selectDrop(index) {
  const items = DROPS_LIST?.querySelectorAll('.drop-item');
  if (!items || items.length === 0) return;

  // Clear previous selection
  items.forEach((item) => item.setAttribute('aria-selected', 'false'));

  selectedIndex = Math.max(0, Math.min(index, items.length - 1));
  const selected = items[selectedIndex];
  selected.setAttribute('aria-selected', 'true');
  selected.focus({ preventScroll: false });

  // Scroll into view
  selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function clearSelection() {
  selectedIndex = -1;
  DROPS_LIST?.querySelectorAll('.drop-item').forEach((item) => {
    item.setAttribute('aria-selected', 'false');
  });
}

function activateSelectedDrop() {
  if (selectedIndex < 0 || selectedIndex >= recentDrops.length) return;
  const drop = recentDrops[selectedIndex];
  const item = DROPS_LIST?.querySelectorAll('.drop-item')[selectedIndex];
  if (!item) return;

  // Toggle expanded state
  const isExpanded = item.classList.contains('drop-item-expanded');
  if (isExpanded) {
    // Collapse — if it has a topic, navigate to findings
    if (drop.topic_id) {
      window.location.href = '/findings';
    } else {
      item.classList.remove('drop-item-expanded');
    }
  } else {
    item.classList.add('drop-item-expanded');
  }
}

// --- Recent drops rendering ---

async function loadRecentDrops() {
  try {
    const resp = await fetch('/api/drops?limit=20');
    if (!resp.ok) return;
    const data = await resp.json();
    recentDrops = data.drops || [];
    renderDropsList();
  } catch (err) {
    // Silent — drops list is non-essential
  }
}

function renderDropsList() {
  if (!DROPS_LIST) return;

  if (recentDrops.length === 0) {
    DROPS_LIST.innerHTML = '';
    return;
  }

  let html = '<div class="recent-drops-label">recent</div>';
  recentDrops.forEach((drop, i) => {
    const content = drop.content.length > 100
      ? drop.content.substring(0, 97) + '...'
      : drop.content;
    const time = formatRelativeTime(drop.dropped_at);
    html += `<div class="drop-item" role="option" tabindex="-1" aria-selected="false" data-index="${i}">` +
      `<span class="drop-item-content">${escapeHtml(content)}</span>` +
      `<span class="drop-item-meta">${time}</span>` +
      '</div>';
  });

  DROPS_LIST.innerHTML = html;

  // Click handler for drops
  DROPS_LIST.querySelectorAll('.drop-item').forEach((item) => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.dataset.index, 10);
      setActiveZone('drops');
      selectDrop(idx);
      activateSelectedDrop();
    });
  });
}

// --- Animation ---

function animateDrop(text) {
  if (!VOID) return;

  const item = document.createElement('div');
  item.className = 'falling-item';
  item.textContent = text.length > 80 ? text.substring(0, 77) + '...' : text;
  VOID.appendChild(item);

  item.addEventListener('animationend', () => {
    item.remove();
  });

  dropCount++;
  updateCounter();
}

// --- API ---

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

// --- Utilities ---

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr + 'Z');
  const now = new Date();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}
