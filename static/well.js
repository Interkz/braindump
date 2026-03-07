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

function isUrl(text) {
  return /^https?:\/\//i.test(text) || text.startsWith('www.');
}

function animateDrop(text) {
  if (!VOID) return;

  const item = document.createElement('div');
  item.className = 'falling-item';

  if (isUrl(text)) {
    item.classList.add('falling-item--link');
    const urlLine = document.createElement('div');
    urlLine.className = 'falling-item__url';
    urlLine.textContent = text.length > 80 ? text.substring(0, 77) + '...' : text;
    item.appendChild(urlLine);
    fetchPreview(text, item);
  } else {
    item.textContent = text.length > 80 ? text.substring(0, 77) + '...' : text;
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

async function fetchPreview(url, item) {
  try {
    const resp = await fetch(`/api/preview?url=${encodeURIComponent(url)}`);
    if (!resp.ok || !item.isConnected) return;
    const data = await resp.json();
    if (!data.title && !data.domain) return;
    if (!item.isConnected) return;

    const preview = document.createElement('div');
    preview.className = 'link-preview';
    if (data.title) {
      const title = document.createElement('div');
      title.className = 'link-preview__title';
      title.textContent = data.title;
      preview.appendChild(title);
    }
    const domain = document.createElement('div');
    domain.className = 'link-preview__domain';
    domain.textContent = data.domain;
    preview.appendChild(domain);

    item.appendChild(preview);
  } catch {
    // Silent — preview is non-essential
  }
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
