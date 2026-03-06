// Shared topic color generation
// Produces a consistent HSL color from a topic name via hash

function topicColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 60%, 65%)`;
}

function applyTopicColors() {
  document.querySelectorAll('[data-topic]').forEach((el) => {
    const name = el.getAttribute('data-topic');
    if (name) {
      el.style.borderLeftColor = topicColor(name);
    }
  });
}

document.addEventListener('DOMContentLoaded', applyTopicColors);
