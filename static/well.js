// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const PINNED = document.querySelector('.pinned-drops');

let dropCount = 0;

// Focus input on load
window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
  loadPinnedDrops();
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

    // Send to backend, then animate with the real drop ID
    const drop = await sendDrop(content);
    animateDrop(content, drop?.id);
  }
});

// Handle paste — auto-submit after a brief delay
INPUT?.addEventListener('paste', (e) => {
  setTimeout(async () => {
    const content = INPUT.value.trim();
    if (content && (content.startsWith('http') || content.length > 100)) {
      INPUT.value = '';
      const drop = await sendDrop(content);
      animateDrop(content.length > 60 ? content.substring(0, 57) + '...' : content, drop?.id);
    }
  }, 100);
});

function animateDrop(text, dropId) {
  if (!VOID) return;

  const item = document.createElement('div');
  item.className = 'falling-item';

  const content = document.createElement('span');
  content.textContent = text.length > 80 ? text.substring(0, 77) + '...' : text;
  item.appendChild(content);

  if (dropId) {
    const pinBtn = document.createElement('button');
    pinBtn.className = 'pin-btn';
    pinBtn.innerHTML = '&#128204;';
    pinBtn.title = 'Pin this drop';
    pinBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      togglePin(dropId);
      item.remove();
    });
    item.appendChild(pinBtn);
  }

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
      return null;
    }
    const data = await resp.json();
    return data.drop;
  } catch (err) {
    console.error('Drop error:', err);
    return null;
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

async function loadPinnedDrops() {
  if (!PINNED) return;
  try {
    const resp = await fetch('/api/drops/pinned');
    if (!resp.ok) return;
    const data = await resp.json();
    renderPinnedDrops(data.drops);
  } catch (err) {
    // Silent — pinned section is non-essential
  }
}

function renderPinnedDrops(drops) {
  if (!PINNED) return;
  if (!drops.length) {
    PINNED.innerHTML = '';
    PINNED.classList.remove('has-pins');
    return;
  }
  PINNED.classList.add('has-pins');
  PINNED.innerHTML = '<div class="pinned-header">pinned</div>' +
    drops.map(d => `
      <div class="pinned-item" data-id="${d.id}">
        <span class="pinned-content">${escapeHtml(d.content)}</span>
        <button class="pin-btn pinned" onclick="togglePin(${d.id})" title="Unpin">&#128204;</button>
      </div>
    `).join('');
}

async function togglePin(dropId) {
  try {
    const resp = await fetch(`/api/drops/${dropId}/pin`, { method: 'POST' });
    if (resp.ok) {
      loadPinnedDrops();
    }
  } catch (err) {
    console.error('Pin toggle error:', err);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
