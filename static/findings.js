// Braindump — Findings page interactions
// Handles topic splitting

let currentTopicId = null;
let drops = [];
let groupCount = 0;

async function openSplit(topicId, topicName) {
  currentTopicId = topicId;
  groupCount = 0;

  document.getElementById('split-topic-name').textContent = topicName;

  // Fetch drops for this topic
  try {
    const resp = await fetch(`/api/findings/${topicId}`);
    if (!resp.ok) throw new Error('Failed to load topic');
    const data = await resp.json();
    drops = data.drops || [];
  } catch (err) {
    console.error('Failed to load drops:', err);
    return;
  }

  if (drops.length < 2) {
    return; // Can't split a topic with fewer than 2 drops
  }

  // Render drops
  const dropsEl = document.getElementById('split-drops');
  dropsEl.innerHTML = '<div class="split-label">assign each drop to a group</div>';
  drops.forEach(drop => {
    const el = document.createElement('div');
    el.className = 'split-drop-item';
    el.dataset.dropId = drop.id;

    const preview = drop.content.length > 120
      ? drop.content.substring(0, 117) + '...'
      : drop.content;

    el.innerHTML = `
      <div class="split-drop-content">${escapeHtml(preview)}</div>
      <select class="split-drop-group" data-drop-id="${drop.id}">
        <option value="">unassigned</option>
      </select>
    `;
    dropsEl.appendChild(el);
  });

  // Reset groups and add two initial groups
  const groupsEl = document.getElementById('split-groups');
  groupsEl.innerHTML = '';
  addGroup();
  addGroup();

  // Show modal
  document.getElementById('split-modal').classList.remove('hidden');
}

function closeSplit() {
  document.getElementById('split-modal').classList.add('hidden');
  currentTopicId = null;
  drops = [];
  groupCount = 0;
}

function addGroup() {
  groupCount++;
  const groupsEl = document.getElementById('split-groups');

  const groupEl = document.createElement('div');
  groupEl.className = 'split-group';
  groupEl.dataset.groupNum = groupCount;
  groupEl.innerHTML = `
    <input type="text" class="split-group-name" placeholder="group ${groupCount} name" data-group="${groupCount}">
  `;
  groupsEl.appendChild(groupEl);

  // Update all dropdowns
  updateGroupSelects();
}

function updateGroupSelects() {
  const selects = document.querySelectorAll('.split-drop-group');
  selects.forEach(sel => {
    const currentVal = sel.value;
    // Keep unassigned option, rebuild group options
    sel.innerHTML = '<option value="">unassigned</option>';
    for (let i = 1; i <= groupCount; i++) {
      const nameInput = document.querySelector(`.split-group-name[data-group="${i}"]`);
      const label = nameInput?.value || `group ${i}`;
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = label;
      sel.appendChild(opt);
    }
    // Restore selection
    if (currentVal && parseInt(currentVal) <= groupCount) {
      sel.value = currentVal;
    }
  });
}

// Update dropdown labels when group names change
document.addEventListener('input', (e) => {
  if (e.target.classList.contains('split-group-name')) {
    updateGroupSelects();
  }
});

async function confirmSplit() {
  // Build groups from selections
  const groupMap = {}; // groupNum -> { name, drop_ids }

  for (let i = 1; i <= groupCount; i++) {
    const nameInput = document.querySelector(`.split-group-name[data-group="${i}"]`);
    const name = nameInput?.value?.trim();
    if (!name) {
      alert(`Please name group ${i}`);
      return;
    }
    groupMap[i] = { name: name, summary: '', drop_ids: [] };
  }

  // Assign drops to groups
  const selects = document.querySelectorAll('.split-drop-group');
  let unassigned = 0;
  selects.forEach(sel => {
    const groupNum = sel.value;
    const dropId = parseInt(sel.dataset.dropId);
    if (!groupNum) {
      unassigned++;
      return;
    }
    groupMap[groupNum].drop_ids.push(dropId);
  });

  // Validate
  const groups = Object.values(groupMap).filter(g => g.drop_ids.length > 0);
  if (groups.length < 2) {
    alert('Assign drops to at least 2 groups');
    return;
  }

  // Send to API
  try {
    const resp = await fetch(`/api/topics/${currentTopicId}/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(err.error || 'Split failed');
      return;
    }

    // Reload page to show new topics
    window.location.reload();
  } catch (err) {
    console.error('Split error:', err);
    alert('Failed to split topic');
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
