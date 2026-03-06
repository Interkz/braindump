// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const RECENT_LIST = document.querySelector('.recent-drops-list');

let dropCount = 0;

// Focus input on load
window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
  loadRecentDrops();
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
    const drop = await sendDrop(content);

    // Add to recent list
    if (drop) {
      prependRecentDrop(drop);
    }
  }
});

// Handle paste — auto-submit after a brief delay
INPUT?.addEventListener('paste', (e) => {
  setTimeout(async () => {
    const content = INPUT.value.trim();
    if (content && (content.startsWith('http') || content.length > 100)) {
      INPUT.value = '';
      animateDrop(content.length > 60 ? content.substring(0, 57) + '...' : content);
      const drop = await sendDrop(content);
      if (drop) {
        prependRecentDrop(drop);
      }
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
    if (resp.ok) {
      const data = await resp.json();
      return data.drop;
    }
    console.error('Drop failed:', resp.status);
  } catch (err) {
    console.error('Drop error:', err);
  }
  return null;
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

// === Recent Drops ===

async function loadRecentDrops() {
  if (!RECENT_LIST) return;
  try {
    const resp = await fetch('/api/drops?limit=20');
    if (resp.ok) {
      const data = await resp.json();
      RECENT_LIST.innerHTML = '';
      (data.drops || []).forEach(drop => {
        RECENT_LIST.appendChild(createDropElement(drop));
      });
    }
  } catch (err) {
    // Silent
  }
}

function prependRecentDrop(drop) {
  if (!RECENT_LIST) return;
  const el = createDropElement(drop);
  RECENT_LIST.prepend(el);
}

function createDropElement(drop) {
  const el = document.createElement('div');
  el.className = 'recent-drop';
  el.dataset.id = drop.id;

  const text = document.createElement('span');
  text.className = 'recent-drop-text';
  text.textContent = drop.content;

  const btn = document.createElement('button');
  btn.className = 'recent-drop-delete';
  btn.textContent = '\u00d7';
  btn.title = 'Delete';
  btn.addEventListener('click', () => handleDelete(el, btn, drop.id));

  el.appendChild(text);
  el.appendChild(btn);
  return el;
}

async function handleDelete(el, btn, dropId) {
  // First click: enter confirm state
  if (!btn.classList.contains('confirm')) {
    btn.classList.add('confirm');
    btn.textContent = 'confirm?';

    // Reset after 3 seconds if not confirmed
    btn._resetTimeout = setTimeout(() => {
      btn.classList.remove('confirm');
      btn.textContent = '\u00d7';
    }, 3000);
    return;
  }

  // Second click: actually delete
  clearTimeout(btn._resetTimeout);
  btn.disabled = true;

  try {
    const resp = await fetch(`/api/drops/${dropId}`, { method: 'DELETE' });
    if (resp.ok) {
      el.classList.add('fade-out');
      el.addEventListener('animationend', () => el.remove());
      dropCount--;
      updateCounter();
    } else {
      btn.disabled = false;
      btn.classList.remove('confirm');
      btn.textContent = '\u00d7';
    }
  } catch (err) {
    console.error('Delete error:', err);
    btn.disabled = false;
    btn.classList.remove('confirm');
    btn.textContent = '\u00d7';
  }
}
