// Braindump — Toast Notifications
// Lightweight notification system, no dependencies

(function () {
  'use strict';

  let container = null;

  function getContainer() {
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  /**
   * Show a toast notification.
   * @param {string} message - Text to display
   * @param {'success'|'error'} [variant='success'] - Visual style
   * @param {number} [duration=3000] - Auto-dismiss time in ms
   */
  function showToast(message, variant, duration) {
    variant = variant || 'success';
    duration = duration || 3000;

    const toast = document.createElement('div');
    toast.className = 'toast toast--' + variant;
    toast.textContent = message;

    getContainer().appendChild(toast);

    // Trigger slide-in on next frame
    requestAnimationFrame(function () {
      toast.classList.add('toast--visible');
    });

    // Auto-dismiss
    const timer = setTimeout(function () { dismiss(toast); }, duration);

    // Click to dismiss early
    toast.addEventListener('click', function () {
      clearTimeout(timer);
      dismiss(toast);
    });
  }

  function dismiss(toast) {
    toast.classList.remove('toast--visible');
    toast.classList.add('toast--out');
    toast.addEventListener('transitionend', function () {
      toast.remove();
    });
  }

  // Expose globally
  window.showToast = showToast;
})();
