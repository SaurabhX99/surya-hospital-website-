/* ============================================================
   VEDANSH MEDICARE — Main JavaScript
   ============================================================ */

(function () {
  'use strict';

  const API_BASE = 'http://localhost:8000';
  const data = window.VM && window.VM.data;

  /* ── Utility ──────────────────────────────────────────── */
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function svgIcon(path, size) {
    size = size || 24;
    return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" width="${size}" height="${size}">${path}</svg>`;
  }

  function showToast(msg, type) {
    const icons = {
      success: svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>', 20),
      error:   svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>', 20),
      info:    svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>', 20),
    };
    type = type || 'info';
    const container = $('#toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span style="color:var(--color-${type === 'success' ? 'accent' : type === 'error' ? 'emergency' : 'primary'})">${icons[type] || ''}</span><span>${msg}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  /* ── Header Scroll Behaviour ──────────────────────────── */
  function initHeader() {
    const header = $('#site-header');
    if (!header) return;
    let lastY = 0;
    window.addEventListener('scroll', function () {
      const y = window.scrollY;
      if (y > 60) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
      lastY = y;
    }, { passive: true });
  }

  /* ── Mobile Navigation ────────────────────────────────── */
  function initMobileNav() {
    const hamburger  = $('#hamburger-btn');
    const mobileNav  = $('#mobile-nav');
    const closeBtn   = $('#mobile-nav-close');
    const mobileBook = $('#mobile-book-btn');
    if (!hamburger || !mobileNav) return;

    function open() {
      mobileNav.classList.add('open');
      hamburger.classList.add('active');
      hamburger.setAttribute('aria-expanded', 'true');
      document.body.classList.add('nav-open');
    }
    function close() {
      mobileNav.classList.remove('open');
      hamburger.classList.remove('active');
      hamburger.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('nav-open');
    }

    hamburger.addEventListener('click', () =>
      mobileNav.classList.contains('open') ? close() : open()
    );
    if (closeBtn) closeBtn.addEventListener('click', close);

    mobileNav.addEventListener('click', e => {
      if (e.target === mobileNav) close();
    });

    $$('.mobile-nav-link', mobileNav).forEach(link => {
      link.addEventListener('click', close);
    });

    if (mobileBook) {
      mobileBook.addEventListener('click', e => {
        e.preventDefault();
        close();
        setTimeout(() => {
          const el = $('#appointment');
          if (el) el.scrollIntoView({ behavior: 'smooth' });
        }, 300);
      });
    }
  }

  /* ── Hero Slider ──────────────────────────────────────── */
  function initHeroSlider(cfg) {
    cfg = cfg || {};
    const interval   = cfg.interval   || 5000;
    const autoplay   = cfg.autoplay   !== false;
    const transition = cfg.transition || 'fade';

    const container = $('#hero-slides');
    if (container) {
      container.dataset.transition = transition;
      // Add transition class to section for CSS targeting
      const heroEl = $('#hero');
      if (heroEl) heroEl.dataset.transition = transition;
    }

    const slides   = $$('.hero-slide');
    const dotsWrap = $('#hero-dots');
    const prevBtn  = $('#hero-prev');
    const nextBtn  = $('#hero-next');
    if (!slides.length) return;

    let current = 0;
    let timer   = null;

    function goTo(idx) {
      slides[current].classList.remove('active');
      $$('.hero-dot', dotsWrap)[current]?.classList.remove('active');
      current = (idx + slides.length) % slides.length;
      slides[current].classList.add('active');
      $$('.hero-dot', dotsWrap)[current]?.classList.add('active');
    }

    function startAuto() {
      clearInterval(timer);
      if (autoplay && slides.length > 1) {
        timer = setInterval(() => goTo(current + 1), interval);
      }
    }

    if (dotsWrap) {
      dotsWrap.innerHTML = '';
      slides.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.className = 'hero-dot' + (i === 0 ? ' active' : '');
        dot.setAttribute('aria-label', `Slide ${i + 1}`);
        dot.dataset.index = i;
        dot.addEventListener('click', () => { goTo(i); startAuto(); });
        dotsWrap.appendChild(dot);
      });
    }

    if (prevBtn) prevBtn.addEventListener('click', () => { goTo(current - 1); startAuto(); });
    if (nextBtn) nextBtn.addEventListener('click', () => { goTo(current + 1); startAuto(); });

    startAuto();
  }

  /* ── Media Gallery Section ────────────────────────────── */
  async function initMediaGallery() {
    // Hero still runs with its own default gradient slide
    initHeroSlider();

    const section = $('#media-gallery-section');
    if (!section) return;

    let media = [], cfg = {};
    try {
      [media, cfg] = await Promise.all([
        fetch(API_BASE + '/api/media?gallery=true').then(r => r.json()),
        fetch(API_BASE + '/api/gallery-config').then(r => r.json()),
      ]);
    } catch (e) { return; }

    if (!media || !media.length) {
      section.style.display = 'none';
      return;
    }

    section.style.display = '';

    const interval   = cfg.interval   || 5000;
    const autoplay   = cfg.autoplay   !== false;
    const transition = cfg.transition || 'fade';
    const captions   = cfg.show_captions !== false;

    // Apply transition type
    const track = $('#gallery-track');
    if (track) track.dataset.transition = transition;

    // Build slides
    if (track) {
      track.innerHTML = '';
      media.forEach((item, i) => {
        const slide = document.createElement('div');
        slide.className = 'gallery-slide' + (i === 0 ? ' active' : '');

        if (item.type === 'video') {
          slide.innerHTML = `
            <div class="gallery-slide-inner">
              <iframe src="${item.display_url}"
                frameborder="0" allow="autoplay; fullscreen" allowfullscreen
                style="position:absolute;inset:0;width:100%;height:100%;border:none;"></iframe>
              ${captions && item.alt ? `<div class="gallery-caption">${item.alt}</div>` : ''}
            </div>`;
        } else {
          slide.innerHTML = `
            <div class="gallery-slide-inner">
              <img src="${item.display_url}"
                   alt="${item.alt || item.title}"
                   style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;"
                   onerror="this.style.display='none';this.parentElement.style.background='#1a2a3a';" />
              ${captions && item.alt ? `<div class="gallery-caption">${item.alt}</div>` : ''}
            </div>`;
        }
        track.appendChild(slide);
      });
    }

    // Build dots
    const dotsEl = $('#gallery-dots');
    if (dotsEl) {
      dotsEl.innerHTML = '';
      media.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.className = 'gallery-dot' + (i === 0 ? ' active' : '');
        dot.setAttribute('aria-label', `Slide ${i + 1}`);
        dotsEl.appendChild(dot);
      });
    }

    // Slider logic
    const slides  = () => track ? Array.from(track.querySelectorAll('.gallery-slide')) : [];
    const dots    = () => dotsEl ? Array.from(dotsEl.querySelectorAll('.gallery-dot')) : [];
    let current   = 0;
    let timer     = null;

    function goTo(idx) {
      const sl = slides(), dt = dots();
      sl[current]?.classList.remove('active');
      dt[current]?.classList.remove('active');
      current = (idx + sl.length) % sl.length;
      sl[current]?.classList.add('active');
      dt[current]?.classList.add('active');
    }

    function startAuto() {
      clearInterval(timer);
      if (autoplay && slides().length > 1) {
        timer = setInterval(() => goTo(current + 1), interval);
      }
    }

    dots().forEach((dot, i) => dot.addEventListener('click', () => { goTo(i); startAuto(); }));
    $('#gallery-prev')?.addEventListener('click', () => { goTo(current - 1); startAuto(); });
    $('#gallery-next')?.addEventListener('click', () => { goTo(current + 1); startAuto(); });

    startAuto();
  }

  /* ── Animated Counter ─────────────────────────────────── */
  function animateCounter(el, target, suffix, duration) {
    suffix   = suffix   || '';
    duration = duration || 2000;
    const start    = performance.now();
    const isLarge  = target > 999;

    function update(now) {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased    = 1 - Math.pow(1 - progress, 3);
      const value    = Math.floor(eased * target);
      el.textContent = isLarge
        ? (value >= 1000 ? (value / 1000).toFixed(1) + 'K' : value) + suffix
        : value + suffix;
      if (progress < 1) requestAnimationFrame(update);
      else el.textContent = (isLarge && target >= 1000)
        ? (target / 1000).toFixed(0) + 'K' + suffix
        : target + suffix;
    }
    requestAnimationFrame(update);
  }

  /* ── Intersection Observer (scroll animations + counters) */
  function initScrollAnimations() {
    const animEls = $$('[data-animate]');
    const countEls = $$('[data-count]');

    const animObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          animObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    animEls.forEach(el => animObserver.observe(el));

    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el     = entry.target;
          const target = parseInt(el.dataset.count, 10);
          const suffix = el.dataset.suffix || '';
          animateCounter(el, target, suffix);
          counterObserver.unobserve(el);
        }
      });
    }, { threshold: 0.5 });

    countEls.forEach(el => counterObserver.observe(el));
  }

  /* ── Render: Specialities ─────────────────────────────── */
  function renderSpecialities() {
    const grid = $('#specialities-grid');
    if (!grid || !data) return;
    grid.innerHTML = data.specialities.map((s, i) => `
      <div class="speciality-card" data-animate="fade-up" data-delay="${(i % 5) * 100}">
        <div class="speciality-icon">${s.icon}</div>
        <h3 class="speciality-name">${s.name}</h3>
        <p class="speciality-desc">${s.desc}</p>
        <a href="specialities.html#${s.id}" class="speciality-link">
          Learn More
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg>
        </a>
      </div>
    `).join('');
  }

  /* ── Render: Why Choose Us ────────────────────────────── */
  function renderFeatures() {
    const grid = $('.why-us-features');
    if (!grid || !data) return;
    grid.innerHTML = data.features.map(f => `
      <div class="feature-card" data-animate="fade-up">
        <div class="feature-icon" style="background:${f.iconBg};">
          <span style="color:${f.iconColor};">${f.icon}</span>
        </div>
        <h4 class="feature-title">${f.title}</h4>
        <p class="feature-desc">${f.desc}</p>
      </div>
    `).join('');
  }

  /* ── Render: Facilities ───────────────────────────────── */
  function renderFacilities(filter) {
    const grid = $('#facilities-grid');
    if (!grid || !data) return;
    filter = filter || 'all';
    const items = filter === 'all'
      ? data.facilities
      : data.facilities.filter(f => f.category === filter);

    grid.innerHTML = items.map((f, i) => `
      <div class="facility-card" data-animate="scale" data-delay="${(i % 4) * 100}">
        <div style="width:100%;height:100%;background:linear-gradient(135deg,${f.color}22,${f.color}55);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;">
          <div style="width:80px;height:80px;background:${f.color};border-radius:20px;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 24px ${f.color}66;">
            ${svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>', 40).replace('stroke="currentColor"', 'stroke="white"')}
          </div>
          <span style="font-family:var(--font-heading);font-size:var(--text-base);font-weight:var(--font-bold);color:${f.color};">${f.name}</span>
        </div>
        <div class="facility-overlay">
          <div class="facility-label">${f.name}</div>
          <div class="facility-desc-overlay">${f.desc}</div>
        </div>
      </div>
    `).join('');

    initScrollAnimations();
  }

  function initFacilitiesFilter() {
    const filterBtns = $$('.filter-btn', $('#facilities-filter'));
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderFacilities(btn.dataset.filter);
      });
    });
  }

  /* ── Render: Doctors ──────────────────────────────────── */
  function _renderDoctorCards(doctors) {
    const grid = $('#doctors-grid');
    if (!grid) return;
    grid.innerHTML = doctors.map((d, i) => `
      <div class="doctor-card" data-animate="fade-up" data-delay="${i * 100}">
        <div class="doctor-photo-wrap" style="position:relative;overflow:hidden;">
          <div style="width:100%;height:100%;background:linear-gradient(135deg,var(--color-bg-section),var(--color-border));display:flex;align-items:center;justify-content:center;">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="var(--color-border)" stroke-width="1" width="80" height="80"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          </div>
          ${d.photo ? `<img src="${d.photo}" alt="${d.name}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none'" />` : ''}
        </div>
        <div class="doctor-card-body">
          <h3 class="doctor-name" style="text-transform:uppercase;letter-spacing:0.04em;">${d.name}</h3>
          <span class="doctor-dept-badge">${d.department}</span>
          <p class="doctor-specialty" style="margin-top:4px;">${d.specialty}</p>
          <p class="doctor-qualification">${d.qualification}</p>
          <div class="doctor-meta">
            <span class="doctor-meta-item">
              ${svgIcon('<circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6l4 2"/>', 12)}
              ${d.experience}
            </span>
            <span class="doctor-meta-item">
              ${svgIcon('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>', 12)}
              ${d.timing}
            </span>
          </div>
          <div class="doctor-actions">
            <a href="#appointment" onclick="_prefillDoctor('${d.name.replace(/'/g, "\\'")}','${(d.department||'').replace(/'/g, "\\'")}');" class="btn btn-primary" style="flex:1;justify-content:center;font-size:var(--text-sm);padding:var(--space-2) var(--space-4);">Book Consult</a>
          </div>
        </div>
      </div>
    `).join('');
  }

  async function renderDoctors() {
    const grid = $('#doctors-grid');
    if (!grid) return;
    try {
      const res = await fetch('http://localhost:8000/api/doctors?featured=true');
      const doctors = await res.json();
      if (doctors.length) { _renderDoctorCards(doctors); return; }
    } catch(e) { /* fall through to static data */ }
    _renderDoctorCards(data.doctors);
  }

  /* ── Render: Testimonials (fetched from API) ──────────── */
  async function renderTestimonials() {
    const track = $('#testimonials-track');
    const dotsEl = $('#test-dots');
    const section = $('#testimonials');
    if (!track) return;

    let items = [];
    try {
      const res = await fetch(API_BASE + '/api/testimonials');
      items = await res.json();
    } catch (e) { /* API offline — hide section */ }

    if (!items.length) {
      if (section) section.style.display = 'none';
      return;
    }
    if (section) section.style.display = '';

    function stars(n) {
      return Array(Math.min(5, Math.max(1, n))).fill(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`
      ).join('');
    }

    function initials(name) {
      return (name || '').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    }

    function fmt(iso) {
      if (!iso) return '';
      return new Date(iso).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    }

    track.innerHTML = items.map(t => `
      <div class="testimonial-card">
        <div class="testimonial-stars">${stars(t.rating)}</div>
        <p class="testimonial-text">${t.text}</p>
        <div class="testimonial-author">
          <div class="testimonial-avatar-placeholder">${initials(t.name)}</div>
          <div>
            <div class="testimonial-name">${t.name}</div>
            <div class="testimonial-date">${fmt(t.created_at)}</div>
          </div>
        </div>
      </div>
    `).join('');

    /* Carousel logic */
    let current = 0;

    function getPerPage() {
      return window.innerWidth > 1024 ? 3 : window.innerWidth > 640 ? 2 : 1;
    }

    function getCardWidth() {
      const pp = getPerPage();
      return (track.parentElement.offsetWidth - 24 * (pp - 1)) / pp;
    }

    function setWidths() {
      const w = getCardWidth();
      $$('.testimonial-card', track).forEach(c => { c.style.flex = `0 0 ${w}px`; });
    }

    function goTo(idx) {
      const pp  = getPerPage();
      const max = Math.max(0, items.length - pp);
      current = Math.max(0, Math.min(idx, max));
      track.style.transform = `translateX(-${current * (getCardWidth() + 24)}px)`;
      if (dotsEl) {
        $$('button', dotsEl).forEach((b, i) => b.classList.toggle('active', i === current));
      }
    }

    if (dotsEl) {
      const pp    = getPerPage();
      const total = Math.max(1, items.length - pp + 1);
      dotsEl.innerHTML = Array(total).fill(0).map((_, i) =>
        `<button style="width:8px;height:8px;border-radius:9999px;background:${i === 0 ? 'var(--color-primary)' : 'var(--color-border)'};border:none;cursor:pointer;transition:all 0.25s;" aria-label="Slide ${i + 1}"></button>`
      ).join('');
      $$('button', dotsEl).forEach((b, i) => b.addEventListener('click', () => goTo(i)));
    }

    const prev = $('#test-prev');
    const next = $('#test-next');
    if (prev) prev.addEventListener('click', () => goTo(current - 1));
    if (next) next.addEventListener('click', () => goTo(current + 1));

    setWidths();
    window.addEventListener('resize', () => { setWidths(); goTo(current); });

    setInterval(() => {
      const max = Math.max(0, items.length - getPerPage());
      goTo(current >= max ? 0 : current + 1);
    }, 5000);
  }

  /* ── Render: Statistics ───────────────────────────────── */
  function renderStats() {
    const grid = $('#stats-grid');
    if (!grid || !data) return;
    grid.innerHTML = data.stats.map((s, i) => `
      <div class="stat-item" data-animate="scale" data-delay="${i * 100}">
        <div class="stat-icon">${s.icon}</div>
        <span class="stat-number" data-count="${s.count}" data-suffix="${s.suffix}">0</span>
        <span class="stat-label">${s.label}</span>
      </div>
    `).join('');
  }

  /* ── Render: Insurance Partners ───────────────────────── */
  function renderPartners() {
    const track = $('#insurance-track');
    if (!track || !data) return;

    const makeLogos = () => data.partners.map(p => `
      <div class="partner-logo">
        <span style="font-size:var(--text-sm);font-weight:var(--font-semibold);color:var(--color-text-secondary);white-space:nowrap;">${p}</span>
      </div>
    `).join('');

    /* Duplicate for infinite scroll */
    track.innerHTML = makeLogos() + makeLogos();
  }

  /* ── Render: Blogs ────────────────────────────────────── */
  async function renderBlogs() {
    const grid = $('#blogs-grid');
    if (!grid) return;
    const categoryColors = {
      'Cardiology': '#E53935',
      'Nephrology': '#0A4D8C',
      'Maternity':  '#E91E8C',
    };
    let blogs = [];
    try {
      const res = await fetch(API_BASE + '/api/blogs');
      blogs = await res.json();
    } catch(e) { return; }
    if (!blogs.length) return;
    grid.innerHTML = blogs.slice(0, 3).map((b, i) => `
      <div class="blog-card" data-animate="fade-up" data-delay="${i * 100}">
        <div class="blog-image-wrap">
          <div style="width:100%;height:100%;background:linear-gradient(135deg,${categoryColors[b.category] || 'var(--color-primary)'}22,${categoryColors[b.category] || 'var(--color-primary)'}44);display:flex;align-items:center;justify-content:center;">
            ${svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>', 64).replace('stroke="currentColor"', `stroke="${categoryColors[b.category] || 'var(--color-primary)'}" opacity="0.4"`)}
          </div>
          <span class="blog-category-badge" style="background:${categoryColors[b.category] || 'var(--color-secondary)'};">${b.category}</span>
        </div>
        <div class="blog-card-body">
          <div class="blog-meta">
            <span class="blog-meta-item">
              ${svgIcon('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>', 12)}
              ${b.created_at ? new Date(b.created_at).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'}) : ''}
            </span>
          </div>
          <h3 class="blog-title">${b.title}</h3>
          <p class="blog-excerpt">${b.excerpt || ''}</p>
          <div class="blog-footer">
            <div class="blog-author">
              <div class="blog-author-avatar" style="background:var(--color-bg-section);display:flex;align-items:center;justify-content:center;">
                ${svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>', 16)}
              </div>
              ${b.author}
            </div>
            <a href="blogs.html" class="btn btn-sm btn-outline" style="font-size:var(--text-xs);">Read More</a>
          </div>
        </div>
      </div>
    `).join('');
  }

  /* ── Populate Department Dropdown + Doctor Datalist ───── */
  let _allDoctors = [];

  function updateDoctorDatalist(deptName) {
    const dl = document.getElementById('doctor-list');
    if (!dl) return;
    dl.innerHTML = '';
    const filtered = deptName
      ? _allDoctors.filter(d => d.department && d.department.toUpperCase() === deptName.toUpperCase())
      : _allDoctors;
    filtered.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.name;
      dl.appendChild(opt);
    });
  }

  async function populateDeptSelect() {
    const sel = $('#appt-dept');
    if (!sel) return;
    try {
      const [deptRes, docRes] = await Promise.all([
        fetch(API_BASE + '/api/departments'),
        fetch(API_BASE + '/api/doctors'),
      ]);
      const depts = await deptRes.json();
      _allDoctors = await docRes.json();

      depts.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.name;
        opt.textContent = d.name;
        sel.appendChild(opt);
      });

      // Wire dept change → rebuild doctor datalist
      sel.addEventListener('change', () => updateDoctorDatalist(sel.value));
      // Populate datalist with all doctors initially
      updateDoctorDatalist('');
    } catch(e) { /* keep placeholder only */ }
  }

  /* ── Appointment Form ─────────────────────────────────── */
  function initAppointmentForm() {
    const form    = $('#appointment-form');
    const success = $('#appt-success');
    const submit  = $('#appt-submit');
    if (!form) return;

    /* Pre-fill doctor/dept from URL params (when coming from doctors.html) */
    const _qs = new URLSearchParams(window.location.search);
    const doctorParam = _qs.get('doctor');
    const deptParam   = _qs.get('dept');
    if (doctorParam || deptParam) {
      // Wait for populateDeptSelect to finish populating the dept dropdown
      setTimeout(() => {
        if (deptParam) {
          const deptEl = $('#appt-dept');
          if (deptEl) {
            deptEl.value = deptParam;
            deptEl.dispatchEvent(new Event('change'));
          }
        }
        if (doctorParam && $('#appt-doctor')) {
          $('#appt-doctor').value = doctorParam;
        }
        const apptSection = $('#appointment');
        if (apptSection) apptSection.scrollIntoView({ behavior: 'smooth' });
      }, 600);
    }

    /* Set min date to today */
    const dateInput = $('#appt-date');
    if (dateInput) {
      const today = new Date().toISOString().split('T')[0];
      dateInput.setAttribute('min', today);
    }

    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      /* Basic validation */
      const name   = $('#appt-name').value.trim();
      const mobile = $('#appt-mobile').value.trim();
      const dept   = $('#appt-dept').value;

      if (!name) {
        showToast('Please enter your full name.', 'error');
        $('#appt-name').focus();
        return;
      }
      if (!mobile || !/^[0-9+\-\s]{10,15}$/.test(mobile)) {
        showToast('Please enter a valid mobile number.', 'error');
        $('#appt-mobile').focus();
        return;
      }
      if (!dept) {
        showToast('Please select a department.', 'error');
        $('#appt-dept').focus();
        return;
      }

      /* Submit to API */
      const spinnerHtml = `
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" width="18" height="18" style="animation:spin 1s linear infinite"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        Submitting…`;
      const confirmHtml = `
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        Confirm Appointment`;

      submit.disabled = true;
      submit.innerHTML = spinnerHtml;

      const doctor  = $('#appt-doctor')  ? $('#appt-doctor').value.trim()  : '';
      const date    = $('#appt-date')    ? $('#appt-date').value            : '';
      const message = $('#appt-message') ? $('#appt-message').value         : '';

      try {
        const res  = await fetch(API_BASE + '/api/appointments', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ name, mobile, department: dept, doctor: doctor || undefined, date, message }),
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || 'Submission failed');

        submit.disabled  = false;
        submit.innerHTML = confirmHtml;
        if (success) success.classList.remove('hidden');
        form.reset();
        showToast("Appointment confirmed! We'll call you within 30 minutes.", 'success');
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (err) {
        submit.disabled  = false;
        submit.innerHTML = confirmHtml;
        showToast('Submission failed. Please call +91 9650494019 directly.', 'error');
      }
    });
  }

  /* ── Smooth Scroll for anchor links ──────────────────────*/
  function initSmoothScroll() {
    $$('a[href^="#"]').forEach(link => {
      link.addEventListener('click', function (e) {
        const target = $(this.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        const headerH = document.getElementById('site-header')?.offsetHeight || 80;
        const top = target.getBoundingClientRect().top + window.scrollY - headerH - 16;
        window.scrollTo({ top, behavior: 'smooth' });
      });
    });
  }

  /* ── Active Nav on Scroll ─────────────────────────────── */
  function initActiveNav() {
    const sections = $$('section[id]');
    const navLinks = $$('.nav-link');
    if (!sections.length || !navLinks.length) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          navLinks.forEach(link => {
            const href = link.getAttribute('href');
            link.classList.toggle('active', href === `#${id}` || (href === 'index.html' && id === 'hero'));
          });
        }
      });
    }, { rootMargin: '-40% 0px -50% 0px' });

    sections.forEach(s => observer.observe(s));
  }

  /* ── Footer Year ──────────────────────────────────────── */
  function setFooterYear() {
    const el = $('#footer-year');
    if (el) el.textContent = new Date().getFullYear();
  }

  /* ── Spin keyframe (for submit button) ────────────────── */
  function injectSpinKeyframe() {
    const style = document.createElement('style');
    style.textContent = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }';
    document.head.appendChild(style);
  }

  /* ── Call Dialog (desktop fallback for tel: links) ────── */
  function showCallDialog(number) {
    const existing = document.getElementById('vm-call-dialog');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'vm-call-dialog';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Call us');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.55);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:16px;';

    const phoneIcon = svgIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>', 28).replace('stroke="currentColor"', 'stroke="white"');

    overlay.innerHTML = `
      <div style="background:#fff;border-radius:20px;padding:36px 28px;max-width:340px;width:100%;text-align:center;box-shadow:0 24px 64px rgba(0,0,0,0.25);">
        <div style="width:64px;height:64px;background:#E53935;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
          ${phoneIcon}
        </div>
        <h3 style="font-family:'Poppins',sans-serif;font-size:18px;font-weight:700;color:#1F2937;margin-bottom:6px;">Emergency Helpline</h3>
        <p style="color:#6B7280;font-size:13px;margin-bottom:16px;">Dial this number from your mobile phone</p>
        <div style="font-family:'Poppins',sans-serif;font-size:24px;font-weight:800;color:#0A4D8C;letter-spacing:1px;margin-bottom:24px;">${number}</div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <button id="vm-copy-btn" style="display:flex;align-items:center;justify-content:center;gap:8px;background:#0A4D8C;color:#fff;padding:12px 20px;border-radius:999px;font-weight:600;font-size:14px;border:none;cursor:pointer;width:100%;font-family:inherit;">Copy Number</button>
          <a href="tel:${number.replace(/\s/g,'')}" style="display:flex;align-items:center;justify-content:center;gap:8px;background:#EEF4FA;color:#0A4D8C;padding:12px 20px;border-radius:999px;font-weight:600;font-size:14px;text-decoration:none;">Try via FaceTime / Calling App</a>
        </div>
        <button id="vm-dialog-close" style="margin-top:14px;color:#9CA3AF;font-size:12px;background:none;border:none;cursor:pointer;display:block;width:100%;font-family:inherit;">Dismiss</button>
      </div>
    `;

    document.body.appendChild(overlay);

    function closeDialog() { overlay.remove(); }

    overlay.addEventListener('click', e => { if (e.target === overlay) closeDialog(); });
    document.getElementById('vm-dialog-close').addEventListener('click', closeDialog);
    document.addEventListener('keydown', function onEsc(e) {
      if (e.key === 'Escape') { closeDialog(); document.removeEventListener('keydown', onEsc); }
    });

    const copyBtn = document.getElementById('vm-copy-btn');
    const rawNumber = number.replace(/\s/g, '');
    copyBtn.addEventListener('click', () => {
      const doFallback = () => {
        const ta = document.createElement('textarea');
        ta.value = rawNumber;
        ta.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      };
      (navigator.clipboard ? navigator.clipboard.writeText(rawNumber).catch(doFallback) : Promise.resolve(doFallback()));
      copyBtn.textContent = '✓ Copied!';
      copyBtn.style.background = '#00C853';
      setTimeout(() => { copyBtn.textContent = 'Copy Number'; copyBtn.style.background = '#0A4D8C'; }, 2000);
    });
  }

  /* Expose so whatsapp.js can call it after all scripts load */
  if (window.VM) window.VM.showCallDialog = showCallDialog;

  /* ── Pre-fill doctor (and dept) from card click ──────── */
  function _prefillDoctor(name, dept) {
    const docEl = $('#appt-doctor');
    if (docEl) docEl.value = name;
    if (dept) {
      const deptEl = $('#appt-dept');
      if (deptEl) {
        deptEl.value = dept;
        deptEl.dispatchEvent(new Event('change'));
      }
    }
  }
  window._prefillDoctor = _prefillDoctor;

  /* Intercept tel: links on desktop — show dialog instead of OS handler */
  function initTelLinks() {
    if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return;
    document.addEventListener('click', e => {
      const link = e.target.closest('a[href^="tel:"]');
      if (!link) return;
      e.preventDefault();
      showCallDialog(link.getAttribute('href').replace('tel:', ''));
    });
  }

  /* ── Init All ─────────────────────────────────────────── */
  function init() {
    injectSpinKeyframe();
    setFooterYear();
    initHeader();
    initMobileNav();
    initMediaGallery();
    initSmoothScroll();
    initTelLinks();

    renderSpecialities();
    renderFeatures();
    renderFacilities('all');
    initFacilitiesFilter();
    renderDoctors();
    renderTestimonials();
    renderStats();
    renderPartners();
    renderBlogs();

    populateDeptSelect();
    initAppointmentForm();
    initActiveNav();

    /* Run after DOM is populated */
    setTimeout(initScrollAnimations, 50);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
