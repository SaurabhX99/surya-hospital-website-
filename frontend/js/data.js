/* ============================================================
   VEDANSH MEDICARE — Static Data Store
   Replace with API calls when backend is ready.
   ============================================================ */

const VM = window.VM || {};

VM.data = {

  /* ── Specialities ─────────────────────────────────────── */
  specialities: [
    {
      id: 'cardiology',
      name: 'Cardiology',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>`,
      desc: 'Comprehensive cardiac care using state-of-the-art technology and advanced procedures.',
    },
    {
      id: 'neuroscience',
      name: 'Neuroscience',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>`,
      desc: 'Expert care for stroke, epilepsy, Parkinson's disease, and multiple sclerosis.',
    },
    {
      id: 'gynaecology',
      name: 'Obs & Gynaecology',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      desc: 'Complete women's health services from prenatal care through menopause management.',
    },
    {
      id: 'pediatrics',
      name: 'Pediatrics',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      desc: 'Dedicated care for children from newborns to adolescents by specialist paediatricians.',
    },
    {
      id: 'orthopaedics',
      name: 'Orthopaedics',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`,
      desc: 'Diagnosis, treatment, and rehabilitation of musculoskeletal conditions and joint replacement.',
    },
    {
      id: 'nephrology',
      name: 'Nephrology',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>`,
      desc: 'Advanced kidney care including dialysis, transplantation support and chronic kidney disease management.',
    },
    {
      id: 'dermatology',
      name: 'Dermatology',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11"/></svg>`,
      desc: 'Expert skin, hair, and nail care including cosmetic dermatology and laser treatments.',
    },
    {
      id: 'urology',
      name: 'Urology',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3"/></svg>`,
      desc: 'Comprehensive urological care covering kidney stones, prostate health, and bladder disorders.',
    },
    {
      id: 'ophthalmology',
      name: 'Eye Care',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>`,
      desc: 'Full range of eye care from routine checkups to advanced surgical interventions.',
    },
    {
      id: 'ent',
      name: 'ENT',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/></svg>`,
      desc: 'Ear, nose, and throat care including hearing assessment, sinus surgery, and more.',
    },
  ],

  /* ── Why Choose Us Features ───────────────────────────── */
  features: [
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`,
      iconBg: 'rgba(229,57,53,0.1)',
      iconColor: '#E53935',
      title: '24×7 Emergency',
      desc: 'Round-the-clock emergency services with rapid response teams always on standby.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>`,
      iconBg: 'rgba(10,77,140,0.1)',
      iconColor: '#0A4D8C',
      title: 'Advanced ICU & NICU',
      desc: 'State-of-the-art intensive care units for critical adult and neonatal patients.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>`,
      iconBg: 'rgba(0,166,166,0.1)',
      iconColor: '#00A6A6',
      title: 'Dialysis Centre',
      desc: 'Modern dialysis centre with latest equipment and experienced nephrology team.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>`,
      iconBg: 'rgba(0,200,83,0.1)',
      iconColor: '#00C853',
      title: 'Modular OT',
      desc: 'Advanced modular operation theatres equipped with latest surgical technology.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`,
      iconBg: 'rgba(10,77,140,0.1)',
      iconColor: '#0A4D8C',
      title: 'Expert Specialists',
      desc: 'Recognized specialists across 20+ departments — among the best in the region.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
      iconBg: 'rgba(0,166,166,0.1)',
      iconColor: '#00A6A6',
      title: 'Ambulance Support',
      desc: 'Fully equipped ambulances available round the clock for emergency transport.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>`,
      iconBg: 'rgba(229,57,53,0.1)',
      iconColor: '#E53935',
      title: 'Blood Bank',
      desc: 'In-house blood bank with round-the-clock availability for emergency requirements.',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>`,
      iconBg: 'rgba(0,200,83,0.1)',
      iconColor: '#00C853',
      title: 'Patient-Centric Care',
      desc: 'Every decision is focused on your health, comfort, recovery, and long-term wellness.',
    },
  ],

  /* ── Facilities ───────────────────────────────────────── */
  facilities: [
    { name: 'ICU',               desc: 'Advanced Intensive Care',           category: 'critical',    color: '#0A4D8C' },
    { name: 'NICU',              desc: 'Neonatal Intensive Care Unit',       category: 'maternity',   color: '#00A6A6' },
    { name: 'Emergency Dept.',   desc: '24×7 Emergency & Trauma Care',       category: 'critical',    color: '#E53935' },
    { name: 'Dialysis Centre',   desc: 'Modern Kidney Dialysis Facility',    category: 'critical',    color: '#0A4D8C' },
    { name: 'Modular OT',        desc: 'Advanced Operating Theatres',        category: 'surgery',     color: '#00C853' },
    { name: 'Labour Room',       desc: 'Comfortable Maternity Suite',        category: 'maternity',   color: '#E91E8C' },
    { name: 'Radiology',         desc: 'Digital X-Ray, CT Scan, MRI',        category: 'diagnostics', color: '#673AB7' },
    { name: 'Pathology Lab',     desc: 'NABL Accredited Diagnostic Lab',     category: 'diagnostics', color: '#FF6F00' },
  ],

  /* ── Doctors ──────────────────────────────────────────── */
  doctors: [
    {
      name: 'Dr. [Name]',
      qualification: 'MBBS, MD (General Medicine)',
      specialty: 'General Medicine',
      department: 'General Medicine',
      experience: '10+ Years',
      timing: 'Mon–Sat, 9 AM–5 PM',
    },
    {
      name: 'Dr. [Name]',
      qualification: 'MBBS, MD, DM (Cardiology)',
      specialty: 'Cardiology',
      department: 'Cardiology',
      experience: '15+ Years',
      timing: 'Mon–Fri, 10 AM–4 PM',
    },
    {
      name: 'Dr. [Name]',
      qualification: 'MBBS, MS (Gynaecology)',
      specialty: 'Obstetrics & Gynaecology',
      department: 'Gynaecology',
      experience: '12+ Years',
      timing: 'Mon–Sat, 9 AM–3 PM',
    },
    {
      name: 'Dr. [Name]',
      qualification: 'MBBS, MD (Paediatrics)',
      specialty: 'Paediatrics & Neonatology',
      department: 'Pediatrics',
      experience: '8+ Years',
      timing: 'Mon–Sat, 8 AM–2 PM',
    },
  ],

  /* ── Testimonials ─────────────────────────────────────── */
  testimonials: [
    {
      name: 'Rajesh Kumar',
      text: 'Excellent care from the entire medical team. The doctors were thorough and the nursing staff was extremely helpful. My recovery was faster than expected thanks to their dedicated attention.',
      rating: 5,
      date: 'March 2024',
    },
    {
      name: 'Priya Sharma',
      text: 'I had my delivery at Vedansh Medicare and the experience was truly wonderful. The maternity team made me feel safe and comfortable throughout. Highly recommend to all expecting mothers.',
      rating: 5,
      date: 'January 2024',
    },
    {
      name: 'Anil Gupta',
      text: 'My father was admitted in the ICU after a cardiac episode. The doctors worked tirelessly and he made a full recovery. Grateful beyond words for the emergency team's swift action.',
      rating: 5,
      date: 'April 2024',
    },
    {
      name: 'Sunita Verma',
      text: 'The dialysis centre is very clean and well-managed. Staff is friendly and always on time. It has made a difficult treatment much more manageable for our family.',
      rating: 5,
      date: 'February 2024',
    },
    {
      name: 'Mohit Singh',
      text: 'Had knee replacement surgery here. The orthopaedics team was outstanding. Post-operative care and physiotherapy were excellent. I'm walking pain-free within months.',
      rating: 5,
      date: 'May 2024',
    },
    {
      name: 'Kavita Tiwari',
      text: 'The OPD experience is very smooth — no long waits, courteous staff, and doctors who actually listen. Vedansh Medicare has set a new benchmark for patient care in Greater Noida.',
      rating: 5,
      date: 'June 2024',
    },
  ],

  /* ── Statistics ───────────────────────────────────────── */
  stats: [
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
      count: 12000,
      suffix: '+',
      label: 'Patients Served',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>`,
      count: 100,
      suffix: '+',
      label: 'Bed Capacity',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`,
      count: 50,
      suffix: '+',
      label: 'Specialist Doctors',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>`,
      count: 20,
      suffix: '+',
      label: 'Specialities',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6l4 2"/></svg>`,
      count: 24,
      suffix: '×7',
      label: 'Emergency Care',
    },
  ],

  /* ── Insurance / Partners ─────────────────────────────── */
  partners: [
    'New India Assurance',
    'Star Health Insurance',
    'United India Insurance',
    'HDFC ERGO Health',
    'Bajaj Allianz Health',
    'ICICI Lombard Health',
    'Niva Bupa (Max Bupa)',
    'Reliance General Insurance',
    'Aditya Birla Health',
    'Care Health Insurance',
    'Tata AIG Health',
    'SBI General Insurance',
  ],

  /* ── Blogs ────────────────────────────────────────────── */
  blogs: [
    {
      title: 'Understanding Heart Disease: Warning Signs You Should Never Ignore',
      excerpt: 'Cardiovascular diseases are the leading cause of death worldwide. Learn the early warning signs and when to seek emergency care.',
      category: 'Cardiology',
      date: 'Jun 10, 2024',
      readTime: '5 min read',
      author: 'Cardiology Team',
    },
    {
      title: 'Kidney Health: How to Protect Your Kidneys from Chronic Disease',
      excerpt: 'Chronic kidney disease often develops silently. Discover practical lifestyle changes that can protect your kidneys for the long term.',
      category: 'Nephrology',
      date: 'May 28, 2024',
      readTime: '6 min read',
      author: 'Nephrology Dept.',
    },
    {
      title: 'Pregnancy Care: Your Complete Guide to a Safe & Healthy Delivery',
      excerpt: 'A healthy pregnancy requires the right medical support and lifestyle habits. Our obstetrics team shares their essential guide for expecting mothers.',
      category: 'Maternity',
      date: 'May 15, 2024',
      readTime: '7 min read',
      author: 'Obs & Gynae Team',
    },
  ],

};

window.VM = VM;
