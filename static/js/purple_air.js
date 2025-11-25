(function () {
  const container = document.getElementById('purpleair-widget');
  if (!container) return;

  const src = container.getAttribute('data-url');
  if (!src) {
    container.textContent = 'PurpleAir URL missing.';
    return;
  }

  const showFallback = (msg) => {
    container.innerHTML = `
      <div style="padding:12px;border:1px solid #ccc;border-radius:6px;background:#fafafa;">
        <div style="margin-bottom:8px;">${msg || 'PurpleAir is taking longer than expected.'}</div>
        <a href="${src}" target="_blank" rel="noopener">Open widget in a new tab</a>
      </div>`;
  };

  const loadIframe = () => {
    // Prevent duplicate loads
    if (container.dataset.loaded === '1') return;
    container.dataset.loaded = '1';

    // Skeleton while loading
    container.innerHTML = `
      <div style="height:360px;border:1px solid #ddd;border-radius:6px;overflow:hidden;position:relative;background:#f0f0f0;">
        <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#666;font:14px/1.4 Arial;">
          Loading PurpleAir…
        </div>
      </div>`;

    const frame = document.createElement('iframe');
    frame.src = src;
    frame.loading = 'lazy';
    frame.referrerPolicy = 'no-referrer-when-downgrade';
    frame.sandbox = 'allow-scripts allow-same-origin allow-popups';
    frame.style.width = '100%';
    frame.style.height = '360px';
    frame.style.border = '0';
    frame.style.borderRadius = '6px';

    let slowTimer = setTimeout(() => {
      showFallback('PurpleAir seems slow to respond.');
    }, 6000); // fallback hint after 6s

    frame.addEventListener('load', () => {
      clearTimeout(slowTimer);
      container.innerHTML = '';
      container.appendChild(frame);
    });

    frame.addEventListener('error', () => {
      clearTimeout(slowTimer);
      showFallback('Failed to load PurpleAir.');
    });

    // Start loading
    // If we hit CSP/X-Frame-Options at their side, onerror/fallback will show.
    try {
      // Append immediately so users see progress
      container.appendChild(frame);
    } catch {
      showFallback('Your browser blocked the widget.');
    }
  };

  // Lazy load when in view
  if ('IntersectionObserver' in window) {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          loadIframe();
          obs.disconnect();
        }
      });
    }, { threshold: 0.1 });
    obs.observe(container);
  } else {
    // Older browsers: load after a short delay
    setTimeout(loadIframe, 500);
  }

  // Safety net: if nothing happened in 12s, show fallback
  setTimeout(() => {
    if (container.dataset.loaded !== '1' || !container.querySelector('iframe')) {
      showFallback('Timeout loading PurpleAir.');
    }
  }, 12000);
})();

