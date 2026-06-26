/* ============================================================
   VEDANSH MEDICARE — Shared JS (header, footer, animations)
   Include on every inner page AFTER the page-specific scripts.
   ============================================================ */
(function () {
  'use strict';

  /* Footer year */
  const yr = document.getElementById('footer-year');
  if (yr) yr.textContent = new Date().getFullYear();

  /* Header scroll */
  const header = document.getElementById('site-header');
  if (header) {
    window.addEventListener('scroll', () => {
      header.classList.toggle('scrolled', window.scrollY > 60);
    }, { passive: true });
  }

  /* Mobile nav */
  const hamburger = document.getElementById('hamburger-btn');
  const mobileNav = document.getElementById('mobile-nav');
  const closeBtn  = document.getElementById('mobile-nav-close');

  if (hamburger && mobileNav) {
    const open  = () => { mobileNav.classList.add('open'); hamburger.classList.add('active'); hamburger.setAttribute('aria-expanded','true'); document.body.classList.add('nav-open'); };
    const close = () => { mobileNav.classList.remove('open'); hamburger.classList.remove('active'); hamburger.setAttribute('aria-expanded','false'); document.body.classList.remove('nav-open'); };
    hamburger.addEventListener('click', () => mobileNav.classList.contains('open') ? close() : open());
    if (closeBtn) closeBtn.addEventListener('click', close);
    mobileNav.addEventListener('click', e => { if (e.target === mobileNav) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  }

  /* Scroll animations */
  const animEls = document.querySelectorAll('[data-animate]');
  if (animEls.length) {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); } });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    animEls.forEach(el => obs.observe(el));
  }

  /* Smooth scroll for anchor links */
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      const headerH = header ? header.offsetHeight : 80;
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - headerH - 16, behavior: 'smooth' });
    });
  });

})();
