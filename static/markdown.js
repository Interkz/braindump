// Simple regex-based markdown renderer for drop content
function renderMarkdown(text) {
  // Escape HTML
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Inline code (before other inline formatting)
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic (single *, but not inside bold remnants)
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Markdown links [text](url)
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Auto-link bare URLs not already inside an href or tag
  html = html.replace(/(?<!["=])(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>');

  // Bullet lists
  const lines = html.split('\n');
  const result = [];
  let inList = false;
  for (const line of lines) {
    if (/^\s*- /.test(line)) {
      if (!inList) { result.push('<ul>'); inList = true; }
      result.push('<li>' + line.replace(/^\s*- /, '') + '</li>');
    } else {
      if (inList) { result.push('</ul>'); inList = false; }
      result.push(line);
    }
  }
  if (inList) result.push('</ul>');

  return result.join('\n')
    .replace(/\n/g, '<br>')
    .replace(/<br>(<\/?(?:ul|li)>)/g, '$1')
    .replace(/(<\/?(?:ul|li)>)<br>/g, '$1');
}
