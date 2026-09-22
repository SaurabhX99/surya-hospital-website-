/* ============================================================
   VEDANSH MEDICARE — Aiva Booking Assistant
   ============================================================ */

(function () {
  'use strict';

  const PHONE = '919650494019';

  /* ── Flow Definition ──────────────────────────────────── */
  const FLOW = {
    start: {
      message: 'Hello! 👋 I\'m *Surya*, your Booking Assistant at Vedansh Medicare. How can I help you today?',
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
      message: 'Which department do you need an appointment for?',
      options: [
        { label: 'Cardiology',        next: 'book_doctor', dept: 'CARDIOLOGY' },
        { label: 'Gynaecology',       next: 'book_doctor', dept: 'GYNAECOLOGIST' },
        { label: 'Paediatrics',       next: 'book_doctor', dept: 'PAEDIATRIC' },
        { label: 'Orthopaedic',       next: 'book_doctor', dept: 'ORTHOPEDIC' },
        { label: 'Neurology',         next: 'book_doctor', dept: 'NEURO' },
        { label: 'ENT',               next: 'book_doctor', dept: 'ENT' },
        { label: 'Dermatology',       next: 'book_doctor', dept: 'DERMATOLOGY' },
        { label: 'General Surgery',   next: 'book_doctor', dept: 'GENERAL SURGEON' },
        { label: 'Other',             next: 'book_name', dept: 'Other' },
      ],
    },
    book_doctor: {
      message: 'Fetching available doctors…',
      dynamic: true,
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
      message: 'Please select your *preferred date* for the appointment:',
      datePicker: true,
    },
    book_confirm: {
      message: '✅ *Appointment request received!* Our team will call you within 30 minutes to confirm.\n\nFor immediate help, call *+91 9650494019*.',
      options: [
        { label: '🏠 Main Menu',  next: 'start' },
        { label: '📞 Call Now',   action: 'call' },
      ],
    },
    doctor_info: {
      message: 'Which speciality are you looking for?',
      options: [
        { label: 'Cardiologist',     next: 'doctor_result', dept: 'CARDIOLOGY' },
        { label: 'Gynaecologist',    next: 'doctor_result', dept: 'GYNAECOLOGIST' },
        { label: 'Paediatrician',    next: 'doctor_result', dept: 'PAEDIATRIC' },
        { label: 'Neurologist',      next: 'doctor_result', dept: 'NEURO' },
        { label: 'Orthopaedic',      next: 'doctor_result', dept: 'ORTHOPEDIC' },
        { label: 'ENT Specialist',   next: 'doctor_result', dept: 'ENT' },
        { label: 'Dermatologist',    next: 'doctor_result', dept: 'DERMATOLOGY' },
        { label: 'Ophthalmologist',  next: 'doctor_result', dept: 'OPTHAMOLOGY' },
        { label: 'General Surgeon',  next: 'doctor_result', dept: 'GENERAL SURGEON' },
        { label: 'Other',            next: 'escalate' },
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
      message: '📅 You can book an appointment by:\n1. Using this chat assistant (you\'re already here! 😊)\n2. Calling *+91 9650494019*\n3. Filling the form on our website',
      options: [
        { label: '📅 Book Now',  next: 'book_dept' },
        { label: '🏠 Main Menu', next: 'start' },
      ],
    },
    escalate: {
      message: '👩‍💼 *Connecting you to our team...*\n\nPlease call us directly:\n📞 *+91 9650494019*\n\nOur team is available Mon–Sat, 8 AM – 8 PM.',
      options: [
        { label: '📞 Call Staff',  action: 'call' },
        { label: '🏠 Main Menu',   next: 'start' },
      ],
    },
  };

  /* ── API helpers ──────────────────────────────────────── */
  const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || 'http://localhost:8000';
  const API_KEY  = (window.APP_CONFIG && window.APP_CONFIG.PUBLIC_API_KEY) || '';
  let _pt = sessionStorage.getItem('vm_pt') || '';

  async function _getPageToken() {
    const expiry = Number(sessionStorage.getItem('vm_pt_exp') || 0);
    if (_pt && Date.now() < expiry) return _pt;
    try {
      const r = await fetch(API_BASE + '/api/public-token');
      if (!r.ok) return _pt;
      const d = await r.json();
      _pt = d.token;
      sessionStorage.setItem('vm_pt', _pt);
      sessionStorage.setItem('vm_pt_exp', Date.now() + (d.expires_in - 60) * 1000);
    } catch (_) {}
    return _pt;
  }

  async function _fetchFaqs() {
    const pt  = await _getPageToken();
    try {
      const res = await fetch(API_BASE + '/api/faqs', {
        headers: { 'X-Api-Key': API_KEY, 'X-Page-Token': pt },
      });
      if (!res.ok) return [];
      return await res.json();
    } catch (_) { return []; }
  }

  async function _loadDynamicFaqs() {
    const faqs = await _fetchFaqs();
    if (!faqs || !faqs.length) return; // keep static fallback

    // Build dynamic FAQ options (+ Main Menu at the end)
    FLOW.faq.options = faqs.map((f, i) => ({
      label: f.question,
      next:  'faq_dyn_' + i,
    }));
    FLOW.faq.options.push({ label: '🏠 Main Menu', next: 'start' });

    // Register one FLOW step per answer
    faqs.forEach((f, i) => {
      FLOW['faq_dyn_' + i] = {
        message: f.answer,
        options: [{ label: '🏠 Main Menu', next: 'start' }],
      };
    });
  }

  async function _fetchDoctors(dept) {
    const pt  = await _getPageToken();
    const res = await fetch(API_BASE + '/api/doctors', {
      headers: { 'X-Api-Key': API_KEY, 'X-Page-Token': pt },
    });
    if (!res.ok) return [];
    const all = await res.json();
    if (!dept) return all;
    const q = dept.toLowerCase();
    return all.filter(d => d.department && d.department.toLowerCase() === q);
  }

  function _titleCase(str) {
    return str.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
  }

  async function _showDoctorOptions() {
    const dept = state.collected.department || '';
    typewriterAppend('Looking up available doctors…', 'bot', null);
    try {
      const doctors = await _fetchDoctors(dept);
      const options = doctors.map(d => ({
        label: `👨‍⚕️ ${d.name}`,
        next: 'book_name',
        doctorName: d.name,
      }));
      options.push({ label: 'Any Available Doctor', next: 'book_name', doctorName: '' });
      setTimeout(() => {
        typewriterAppend('Please select a *doctor* for your appointment:', 'bot', () => {
          appendOptions(options);
        });
      }, 400);
    } catch (_) {
      // If fetch fails, skip doctor selection
      setTimeout(() => renderStep('book_name'), 300);
    }
  }

  async function _showDoctorResult() {
    const dept      = state.collected.department || '';
    const deptLabel = _titleCase(dept) || 'Specialist';
    typewriterAppend('Looking up our specialists for you…', 'bot', null);
    try {
      const doctors = await _fetchDoctors(dept);
      if (doctors.length > 0) {
        const list = doctors
          .map(d => `👨‍⚕️ *${d.name}*\n🎓 ${d.qualification} · ${d.experience}\n⏰ ${d.timing}`)
          .join('\n\n');
        FLOW.doctor_result.message =
          `Here are our *${deptLabel}* specialists:\n\n${list}\n\n📅 Book an appointment or call *+91 9650494019* to confirm availability.`;
      } else {
        FLOW.doctor_result.message =
          `Our *${deptLabel}* doctors are available Mon–Sat. Please book an appointment or call us to check current availability.\n📞 *+91 9650494019*`;
      }
    } catch (_) {
      FLOW.doctor_result.message =
        `Our specialists are available Mon–Sat. Please book an appointment or call us directly.\n📞 *+91 9650494019*`;
    }
    setTimeout(() => renderStep('doctor_result'), 300);
  }

  async function _submitAppointment(data) {
    const pt = await _getPageToken();
    const res = await fetch(API_BASE + '/api/appointments', {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key':    API_KEY,
        'X-Page-Token': pt,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to save appointment');
    return await res.json();
  }

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

  function appendDatePicker() {
    const wrap = document.createElement('div');
    wrap.className = 'wa-message wa-message-bot';
    const inner = document.createElement('div');
    inner.style.cssText = 'display:flex;flex-direction:column;gap:8px;width:100%;';

    const dateInput = document.createElement('input');
    dateInput.type = 'date';
    dateInput.style.cssText = 'padding:10px 14px;border:1.5px solid #D1D5DB;border-radius:10px;font-size:14px;font-family:inherit;outline:none;width:100%;box-sizing:border-box;color:#1F2937;background:#fff;';
    // Set min to today
    const today = new Date();
    dateInput.min = today.toISOString().split('T')[0];
    // Default to tomorrow
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInput.value = tomorrow.toISOString().split('T')[0];

    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'wa-option-btn';
    confirmBtn.textContent = '✓ Confirm Date';
    confirmBtn.style.cssText += 'background:var(--color-primary,#0A4D8C);color:#fff;font-weight:600;';
    confirmBtn.addEventListener('click', () => {
      if (!dateInput.value) return;
      const d = new Date(dateInput.value + 'T00:00:00');
      const label = d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
      appendMessage(label, 'user');
      state.collected.date = dateInput.value;
      state.collecting = null;
      _bookAppointment();
    });

    inner.appendChild(dateInput);
    inner.appendChild(confirmBtn);
    wrap.appendChild(inner);
    chat.appendChild(wrap);
    scrollBottom();
  }

  function renderStep(stepKey) {
    const step = FLOW[stepKey];
    if (!step) return;
    state.step = stepKey;

    if (step.dynamic && stepKey === 'book_doctor') {
      _showDoctorOptions();
      return;
    }

    typewriterAppend(step.message, 'bot', () => {
      if (step.options) appendOptions(step.options);
      if (step.datePicker) {
        appendDatePicker();
      }
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
    if (opt.dept) {
      state.collected.department = opt.dept;
    }
    if (opt.doctorName !== undefined) {
      state.collected.doctor = opt.doctorName;
    }

    if (opt.next === 'doctor_result') {
      _showDoctorResult();
      return;
    }

    setTimeout(() => renderStep(opt.next), 300);
  }

  function handleUserInput(text) {
    if (!text.trim()) return;
    appendMessage(text, 'user');
    input.value = '';

    const current = FLOW[state.collecting];
    if (current && current.input && current.next) {
      if (state.collecting === 'book_mobile') {
        const digits = text.replace(/\D/g, '');
        const valid  = /^[6-9]\d{9}$/.test(digits);
        if (!valid) {
          appendMessage('⚠️ Please enter a valid 10-digit Indian mobile number (e.g. 9876543210).', 'bot');
          input.focus();
          return;
        }
        state.collected.mobile = digits;
      } else if (state.collecting === 'book_name') {
        state.collected.name = text;
      }

      input.disabled = true;
      input.placeholder = 'Type a message…';
      state.collecting = null;

      if (current.next === 'book_confirm') {
        _bookAppointment();
      } else {
        setTimeout(() => renderStep(current.next), 400);
      }
    }
  }

  async function _bookAppointment() {
    typewriterAppend('Booking your appointment…', 'bot', null);
    try {
      await _submitAppointment({
        name:       state.collected.name       || '',
        mobile:     state.collected.mobile     || '',
        department: state.collected.department || '',
        doctor:     state.collected.doctor     || '',
        date:       state.collected.date       || '',
        message:    'Booked via Surya chat assistant',
      });
      // Replace static message with a success variant
      FLOW.book_confirm.message =
        '✅ *Appointment booked successfully!* Our team will call you within 30 minutes to confirm.\n\nFor immediate help, call *+91 9650494019*.';
    } catch (_) {
      FLOW.book_confirm.message =
        '⚠️ We received your request but could not save it automatically. Please call *+91 9650494019* to confirm your appointment.\n\nSorry for the inconvenience.';
    }
    setTimeout(() => renderStep('book_confirm'), 400);
  }

  /* ── Toggle Panel ─────────────────────────────────────── */
  function openPanel() {
    state.open = true;
    panel.classList.add('open');
    trigger.setAttribute('aria-expanded', 'true');
    const badge = trigger.querySelector('.wa-badge');
    if (badge) badge.style.display = 'none';

    if (chat.children.length === 0) {
      _loadDynamicFaqs().then(() => setTimeout(() => renderStep('start'), 300));
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
