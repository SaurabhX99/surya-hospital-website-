/* ============================================================
   VEDANSH MEDICARE — WhatsApp AI Assistant
   ============================================================ */

(function () {
  'use strict';

  const PHONE = '919650494019';

  /* ── Flow Definition ──────────────────────────────────── */
  const FLOW = {
    start: {
      message: 'Hello! 👋 Welcome to *Vedansh Medicare*. How can I assist you today?',
      options: [
        { label: '📅 Book Appointment',    next: 'book_dept' },
        { label: '👨‍⚕️ Doctor Info',          next: 'doctor_info' },
        { label: '🏥 OPD Timings',          next: 'opd_timings' },
        { label: '🚨 Emergency Help',       next: 'emergency' },
        { label: '🚑 Ambulance Request',    next: 'ambulance' },
        { label: '❓ FAQ',                  next: 'faq' },
        { label: '📞 Talk to Staff',        next: 'escalate' },
      ],
    },
    book_dept: {
      message: 'Great! Which department do you need an appointment for?',
      options: [
        { label: 'General Medicine',     next: 'book_name', dept: 'General Medicine' },
        { label: 'Cardiology',           next: 'book_name', dept: 'Cardiology' },
        { label: 'Gynaecology',          next: 'book_name', dept: 'Obstetrics & Gynaecology' },
        { label: 'Pediatrics',           next: 'book_name', dept: 'Pediatrics' },
        { label: 'Orthopaedics',         next: 'book_name', dept: 'Orthopaedics' },
        { label: 'Other Dept.',          next: 'book_name', dept: 'Other' },
      ],
    },
    book_name: {
      message: 'Please type your *full name* to continue.',
      input: true,
      next: 'book_mobile',
    },
    book_mobile: {
      message: 'Thanks! Now please share your *mobile number*.',
      input: true,
      next: 'book_date',
    },
    book_date: {
      message: 'What is your *preferred date* for the appointment? (e.g., Tomorrow, Monday, 20 June)',
      input: true,
      next: 'book_confirm',
    },
    book_confirm: {
      message: '✅ *Appointment request received!* Our team will call you within 30 minutes to confirm.\n\nFor immediate help, call *+91 9650494019*.',
      options: [
        { label: '🏠 Main Menu', next: 'start' },
        { label: '📞 Call Now',  action: 'call' },
      ],
    },
    doctor_info: {
      message: 'We have specialist doctors across 20+ departments. Which speciality are you looking for?',
      options: [
        { label: 'Cardiologist',    next: 'doctor_result', dept: 'Cardiology' },
        { label: 'Gynaecologist',   next: 'doctor_result', dept: 'Gynaecology' },
        { label: 'Paediatrician',   next: 'doctor_result', dept: 'Pediatrics' },
        { label: 'Neurologist',     next: 'doctor_result', dept: 'Neuroscience' },
        { label: 'Nephrologist',    next: 'doctor_result', dept: 'Nephrology' },
        { label: 'Other',           next: 'escalate' },
      ],
    },
    doctor_result: {
      message: 'Our specialists are available Mon–Sat. Please *book an appointment* or call us directly to check doctor availability.\n📞 *+91 9650494019*',
      options: [
        { label: '📅 Book Now',    next: 'book_dept' },
        { label: '🏠 Main Menu',   next: 'start' },
      ],
    },
    opd_timings: {
      message: '🕘 *OPD Timings — Vedansh Medicare*\n\n• Morning OPD: 9:00 AM – 1:00 PM\n• Evening OPD: 5:00 PM – 8:00 PM\n• Emergency: 24 Hours / 7 Days\n\nFor specific department timings, please call us.',
      options: [
        { label: '📅 Book Appointment', next: 'book_dept' },
        { label: '🏠 Main Menu',        next: 'start' },
        { label: '📞 Call Us',          action: 'call' },
      ],
    },
    emergency: {
      message: '🚨 *EMERGENCY?*\n\nPlease *call immediately*:\n📞 *+91 9650494019*\n\nOur emergency team is available *24 hours a day, 7 days a week*. Do not wait — call us now!',
      options: [
        { label: '📞 Call Emergency Now', action: 'call' },
        { label: '🚑 Request Ambulance',  next: 'ambulance' },
        { label: '🏠 Main Menu',          next: 'start' },
      ],
    },
    ambulance: {
      message: '🚑 *Ambulance Request*\n\nFor immediate ambulance dispatch, please call:\n📞 *+91 9650494019*\n\nShare your location and our team will reach you as soon as possible.',
      options: [
        { label: '📞 Call for Ambulance', action: 'call' },
        { label: '🏠 Main Menu',          next: 'start' },
      ],
    },
    faq: {
      message: 'Here are our most frequently asked questions:',
      options: [
        { label: 'Do you accept insurance?',     next: 'faq_insurance' },
        { label: 'Is there parking?',            next: 'faq_parking' },
        { label: 'Are you open on Sundays?',     next: 'faq_hours' },
        { label: 'How to book appointment?',     next: 'faq_book' },
        { label: '🏠 Main Menu',                 next: 'start' },
      ],
    },
    faq_insurance: {
      message: '✅ Yes, we accept all major health insurance providers including Star Health, HDFC ERGO, New India Assurance, Bajaj Allianz, ICICI Lombard, and many more. Please carry your insurance card at the time of admission.',
      options: [{ label: '🏠 Main Menu', next: 'start' }],
    },
    faq_parking: {
      message: '🚗 Yes, Vedansh Medicare has dedicated parking facilities for patients and visitors.',
      options: [{ label: '🏠 Main Menu', next: 'start' }],
    },
    faq_hours: {
      message: '🕐 Yes! We are open *24 hours a day, 7 days a week* including Sundays and public holidays. Emergency services are always available.',
      options: [{ label: '🏠 Main Menu', next: 'start' }],
    },
    faq_book: {
      message: '📅 You can book an appointment by:\n1. Using this chat assistant\n2. Calling *+91 9650494019*\n3. Filling the form on our website\n4. WhatsApp: *+91 9650494019*',
      options: [
        { label: '📅 Book Now',  next: 'book_dept' },
        { label: '🏠 Main Menu', next: 'start' },
      ],
    },
    escalate: {
      message: '👩‍💼 *Connecting you to our staff...*\n\nPlease call us directly or continue on WhatsApp:\n📞 *+91 9650494019*\n💬 Our team is available Mon–Sat, 8 AM – 8 PM.',
      options: [
        { label: '📞 Call Staff',     action: 'call' },
        { label: '💬 Open WhatsApp',  action: 'whatsapp' },
        { label: '🏠 Main Menu',      next: 'start' },
      ],
    },
  };

  /* ── State ────────────────────────────────────────────── */
  const state = {
    step: 'start',
    collecting: null,
    collected: {},
    open: false,
  };

  /* ── DOM References ───────────────────────────────────── */
  const trigger  = document.getElementById('wa-trigger');
  const panel    = document.getElementById('wa-panel');
  const closeBtn = document.getElementById('wa-close');
  const chat     = document.getElementById('wa-chat');
  const input    = document.getElementById('wa-input');
  const sendBtn  = document.getElementById('wa-send');

  if (!trigger || !panel) return;

  /* ── Helpers ──────────────────────────────────────────── */
  function formatMessage(text) {
    return text
      .replace(/\*(.*?)\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br/>');
  }

  function scrollBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  function appendMessage(text, role) {
    const wrap = document.createElement('div');
    wrap.className = `wa-message wa-message-${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'wa-bubble';
    bubble.innerHTML = formatMessage(text);
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    scrollBottom();
  }

  function appendOptions(options) {
    const wrap = document.createElement('div');
    wrap.className = 'wa-message wa-message-bot';
    const inner = document.createElement('div');
    inner.className = 'wa-options';
    options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'wa-option-btn';
      btn.textContent = opt.label;
      btn.addEventListener('click', () => handleOption(opt));
      inner.appendChild(btn);
    });
    wrap.appendChild(inner);
    chat.appendChild(wrap);
    scrollBottom();
  }

  function typewriterAppend(text, role, callback) {
    const wrap = document.createElement('div');
    wrap.className = `wa-message wa-message-${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'wa-bubble';
    bubble.innerHTML = '<span class="typing-cursor">▋</span>';
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    scrollBottom();

    setTimeout(() => {
      bubble.innerHTML = formatMessage(text);
      scrollBottom();
      if (callback) callback();
    }, 600);
  }

  function renderStep(stepKey) {
    const step = FLOW[stepKey];
    if (!step) return;
    state.step = stepKey;

    typewriterAppend(step.message, 'bot', () => {
      if (step.options) appendOptions(step.options);
      if (step.input) {
        input.disabled = false;
        input.placeholder = 'Type your answer…';
        input.focus();
        state.collecting = stepKey;
      }
    });
  }

  function handleOption(opt) {
    appendMessage(opt.label, 'user');

    if (opt.action === 'call') {
      const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
      if (isMobile) {
        window.location.href = `tel:+${PHONE}`;
      } else if (window.VM && window.VM.showCallDialog) {
        window.VM.showCallDialog(`+${PHONE}`);
      }
      return;
    }
    if (opt.action === 'whatsapp') {
      window.open(`https://wa.me/${PHONE}`, '_blank', 'noopener');
      return;
    }
    if (opt.dept) {
      state.collected.department = opt.dept;
    }

    setTimeout(() => renderStep(opt.next), 300);
  }

  function handleUserInput(text) {
    if (!text.trim()) return;
    appendMessage(text, 'user');
    input.value = '';

    const current = FLOW[state.collecting];
    if (current && current.input && current.next) {
      if (state.collecting === 'book_name')   state.collected.name   = text;
      if (state.collecting === 'book_mobile') state.collected.mobile = text;
      if (state.collecting === 'book_date')   state.collected.date   = text;

      input.disabled = true;
      input.placeholder = 'Type a message…';
      state.collecting = null;

      setTimeout(() => renderStep(current.next), 400);
    }
  }

  /* ── Toggle Panel ─────────────────────────────────────── */
  function openPanel() {
    state.open = true;
    panel.classList.add('open');
    trigger.setAttribute('aria-expanded', 'true');
    const badge = trigger.querySelector('.wa-badge');
    if (badge) badge.style.display = 'none';

    if (chat.children.length === 0) {
      setTimeout(() => renderStep('start'), 300);
    }
  }

  function closePanel() {
    state.open = false;
    panel.classList.remove('open');
    trigger.setAttribute('aria-expanded', 'false');
  }

  /* ── Event Listeners ──────────────────────────────────── */
  trigger.addEventListener('click', () => state.open ? closePanel() : openPanel());
  closeBtn.addEventListener('click', closePanel);

  sendBtn.addEventListener('click', () => handleUserInput(input.value));
  input.addEventListener('keydown', e => { if (e.key === 'Enter') handleUserInput(input.value); });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && state.open) closePanel();
  });

  document.addEventListener('click', e => {
    if (state.open && !panel.contains(e.target) && !trigger.contains(e.target)) {
      closePanel();
    }
  });

})();
