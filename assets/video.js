// Load only visible films. Keep native player controls and direct watch links
// available when the browser or an extension prevents autoplay.
function loadVideo(link, focus = false) {
  if (!link.isConnected) return;
  const id = link.dataset.youtubeId;
  if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
  const iframe = document.createElement('iframe');
  iframe.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&playsinline=1&rel=0&loop=1&playlist=${id}`;
  iframe.title = link.getAttribute('aria-label').replace(/^Play /, '');
  iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
  iframe.allowFullscreen = true;
  iframe.referrerPolicy = 'strict-origin-when-cross-origin';
  link.replaceWith(iframe);
  if (focus) iframe.focus();
}

const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    observer.unobserve(entry.target);
    loadVideo(entry.target);
  }
}, { threshold: 0.25 }) : null;

for (const link of document.querySelectorAll('a[data-youtube-id]')) {
  observer?.observe(link);
  link.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (!/^[A-Za-z0-9_-]{11}$/.test(link.dataset.youtubeId)) return;
    event.preventDefault();
    observer?.unobserve(link);
    loadVideo(link, true);
  });
}
