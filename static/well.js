// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const RECENT = document.querySelector('.recent-drops');

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
    } else {
      loadRecentDrops();
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

// === Recent Drops & Inline Editing ===

async function loadRecentDrops() {
  if (!RECENT) return;
  try {
    const resp = await fetch('/api/drops?limit=20');
    if (!resp.ok) return;
    const data = await resp.json();
    renderDrops(data.drops || []);
  } catch (err) {
    // Silent — recent drops are non-essential
  }
}

function renderDrops(drops) {
  if (!RECENT) return;
  RECENT.innerHTML = '';
  for (const drop of drops) {
    RECENT.appendChild(createDropItem(drop));
  }
}

function createDropItem(drop) {
  const item = document.createElement('div');
  item.className = 'drop-item';
  item.dataset.id = drop.id;

  const content = document.createElement('span');
  content.className = 'drop-item-content';
  content.textContent = drop.content;
  content.addEventListener('click', () => enterEditMode(item, drop));

  const icon = document.createElement('span');
  icon.className = 'drop-item-edit-icon';
  icon.textContent = '\u270E';
  icon.addEventListener('click', () => enterEditMode(item, drop));

  item.appendChild(content);
  item.appendChild(icon);
  return item;
}

function enterEditMode(item, drop) {
  if (item.classList.contains('editing')) return;
  item.classList.add('editing');

  const content = item.querySelector('.drop-item-content');
  const icon = item.querySelector('.drop-item-edit-icon');
  const originalText = drop.content;

  content.style.display = 'none';
  icon.style.display = 'none';

  const textarea = document.createElement('textarea');
  textarea.className = 'drop-item-textarea';
  textarea.value = originalText;
  item.insertBefore(textarea, content);

  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);

  // Auto-resize
  autoResizeTextarea(textarea);
  textarea.addEventListener('input', () => autoResizeTextarea(textarea));

  function exitEditMode(save) {
    if (!item.classList.contains('editing')) return;
    item.classList.remove('editing');
    const newText = textarea.value.trim();
    textarea.remove();
    content.style.display = '';
    icon.style.display = '';

    if (save && newText && newText !== originalText) {
      content.textContent = newText;
      drop.content = newText;
      saveDrop(drop.id, newText);
    }
  }

  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      exitEditMode(true);
    } else if (e.key === 'Escape') {
      exitEditMode(false);
    }
  });

  textarea.addEventListener('blur', () => exitEditMode(true));
}

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = textarea.scrollHeight + 'px';
}

async function saveDrop(id, content) {
  try {
    const resp = await fetch(`/api/drops/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      console.error('Update drop failed:', resp.status);
    }
  } catch (err) {
    console.error('Update drop error:', err);
  }
}
