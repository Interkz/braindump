// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const TOPICS_EL = document.getElementById('recent-topics');

let dropCount = 0;

// Focus input on load
window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
  loadRecentTopics();
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
    // Refresh topics after background processing has time to run
    setTimeout(loadRecentTopics, 3000);
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

async function loadRecentTopics() {
  if (!TOPICS_EL) return;
  try {
    const resp = await fetch('/api/topics/recent?limit=5');
    if (!resp.ok) return;
    const data = await resp.json();
    const topics = data.topics || [];
    if (topics.length === 0) {
      TOPICS_EL.innerHTML = '';
      return;
    }
    TOPICS_EL.innerHTML =
      '<div class="recent-topics-title">recent topics</div>' +
      topics.map(t =>
        `<a href="/findings#topic-${t.id}" class="recent-topic-item">` +
          `<span class="recent-topic-name">${escapeHtml(t.name)}</span>` +
          `<span class="recent-topic-count">${t.drop_count}</span>` +
        `</a>`
      ).join('');
  } catch (err) {
    // Silent — sidebar is non-essential
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
