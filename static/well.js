// Braindump — The Well
// Handles input, drop animation, and API calls

const VOID = document.querySelector('.the-void');
const INPUT = document.querySelector('.drop-input');
const COUNTER = document.querySelector('.drop-counter');
const STREAK_WIDGET = document.querySelector('.streak-widget');
const STREAK_COUNTER = document.querySelector('.streak-counter');
const STREAK_GRID = document.querySelector('.streak-grid');

let dropCount = 0;

// Focus input on load
window.addEventListener('load', () => {
  INPUT?.focus();
  loadDropCount();
  loadStreak();
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

async function loadStreak() {
  try {
    const resp = await fetch('/api/streak');
    if (!resp.ok) return;
    const data = await resp.json();
    renderStreak(data.streak, data.history);
  } catch (err) {
    // Silent — streak is non-essential
  }
}

function renderStreak(streak, history) {
  if (!STREAK_WIDGET || !STREAK_COUNTER || !STREAK_GRID) return;

  if (streak > 0) {
    STREAK_COUNTER.innerHTML =
      `<span class="streak-flame">\u{1F525}</span> <span class="streak-num">${streak}</span> day${streak === 1 ? '' : 's'}`;
  }

  STREAK_GRID.innerHTML = '';
  for (const day of history) {
    const cell = document.createElement('div');
    cell.className = 'streak-cell';
    const d = new Date(day.date + 'T00:00:00');
    cell.title = `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}: ${day.count} drop${day.count === 1 ? '' : 's'}`;
    if (day.count >= 10) cell.classList.add('level-4');
    else if (day.count >= 5) cell.classList.add('level-3');
    else if (day.count >= 2) cell.classList.add('level-2');
    else if (day.count >= 1) cell.classList.add('level-1');
    STREAK_GRID.appendChild(cell);
  }

  STREAK_WIDGET.classList.add('visible');
}
