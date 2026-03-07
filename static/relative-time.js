// Relative time formatting + auto-refresh

function formatRelativeTime(dateString) {
  // SQLite datetime format: "YYYY-MM-DD HH:MM:SS" (UTC)
  const date = new Date(dateString.replace(' ', 'T') + 'Z');
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 30) return 'just now';
  if (diffMin < 1) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`;
  if (diffDay === 1) return 'yesterday';
  if (diffDay < 7) return `${diffDay} days ago`;

  // Older than a week: show short date
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[date.getMonth()]} ${date.getDate()}`;
}

function formatExactTime(dateString) {
  const date = new Date(dateString.replace(' ', 'T') + 'Z');
  return date.toLocaleString();
}

function refreshRelativeTimes() {
  document.querySelectorAll('[data-timestamp]').forEach(el => {
    const ts = el.getAttribute('data-timestamp');
    el.textContent = formatRelativeTime(ts);
    el.title = formatExactTime(ts);
  });
}

// Init + auto-refresh every 30s
document.addEventListener('DOMContentLoaded', () => {
  refreshRelativeTimes();
  setInterval(refreshRelativeTimes, 30000);
});
