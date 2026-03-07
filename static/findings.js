// Braindump — Findings keyboard navigation

const CARDS = document.querySelectorAll('.topic-card[role="option"]');
let selectedIndex = -1;

// Auto-select first card on load
window.addEventListener('load', () => {
  if (CARDS.length > 0) {
    selectCard(0);
  }
});

document.addEventListener('keydown', (e) => {
  if (CARDS.length === 0) return;

  switch (e.key) {
    case 'ArrowDown':
    case 'j':
      e.preventDefault();
      selectCard(Math.min(selectedIndex + 1, CARDS.length - 1));
      break;

    case 'ArrowUp':
    case 'k':
      e.preventDefault();
      selectCard(Math.max(selectedIndex - 1, 0));
      break;

    case 'Enter':
      e.preventDefault();
      activateCard();
      break;

    case 'Escape':
      e.preventDefault();
      window.location.href = '/';
      break;
  }
});

function selectCard(index) {
  CARDS.forEach((card) => card.setAttribute('aria-selected', 'false'));
  selectedIndex = Math.max(0, Math.min(index, CARDS.length - 1));
  const card = CARDS[selectedIndex];
  card.setAttribute('aria-selected', 'true');
  card.focus({ preventScroll: false });
  card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function activateCard() {
  if (selectedIndex < 0 || selectedIndex >= CARDS.length) return;
  const card = CARDS[selectedIndex];
  const topicId = card.dataset.topicId;
  if (topicId) {
    // Fetch topic details and show drops inline
    toggleTopicDrops(card, topicId);
  }
}

async function toggleTopicDrops(card, topicId) {
  const existing = card.querySelector('.topic-drops');
  if (existing) {
    existing.remove();
    return;
  }

  try {
    const resp = await fetch(`/api/findings/${topicId}`);
    if (!resp.ok) return;
    const data = await resp.json();

    const dropsEl = document.createElement('div');
    dropsEl.className = 'topic-drops';

    if (data.drops && data.drops.length > 0) {
      data.drops.forEach((drop) => {
        const dropEl = document.createElement('div');
        dropEl.className = 'topic-drop-item';
        dropEl.textContent = drop.content;
        dropsEl.appendChild(dropEl);
      });
    } else {
      dropsEl.textContent = 'No drops yet.';
    }

    card.appendChild(dropsEl);
  } catch (err) {
    // Silent
  }
}

// Click support
CARDS.forEach((card, i) => {
  card.addEventListener('click', () => {
    selectCard(i);
    activateCard();
  });
});
