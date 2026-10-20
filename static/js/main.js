/**
 * FarmFresh Rescue - Client-side interactive enhancements
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Toggle & Navigation Drawer
  const menuToggle = document.getElementById('menuToggle');
  const navMenuWrapper = document.getElementById('navMenuWrapper');
  if (menuToggle && navMenuWrapper) {
    menuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', String(!isExpanded));
      menuToggle.classList.toggle('active');
      navMenuWrapper.classList.toggle('active');
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
      if (navMenuWrapper.classList.contains('active')) {
        if (!navMenuWrapper.contains(e.target) && !menuToggle.contains(e.target)) {
          navMenuWrapper.classList.remove('active');
          menuToggle.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
        }
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && navMenuWrapper.classList.contains('active')) {
        navMenuWrapper.classList.remove('active');
        menuToggle.classList.remove('active');
        menuToggle.setAttribute('aria-expanded', 'false');
      }
    });

    // Close menu after clicking nav links on mobile
    navMenuWrapper.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 768) {
          navMenuWrapper.classList.remove('active');
          menuToggle.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
        }
      });
    });
  }

  // 2. Auto-dismiss Flash Alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 500);
    }, 5500);
  });

  // Manual close buttons
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');
      if (alert) alert.remove();
    });
  });

  // 3. Image Upload Live Preview
  const photoInput = document.getElementById('cropPhotoInput');
  const previewImg = document.getElementById('cropPhotoPreview');
  const previewContainer = document.getElementById('imagePreviewContainer');
  const placeholderText = document.getElementById('previewPlaceholderText');

  if (photoInput && previewImg) {
    photoInput.addEventListener('change', function () {
      const file = this.files[0];
      if (file) {
        // Validate size (3MB)
        if (file.size > 3 * 1024 * 1024) {
          alert('File is too large! Maximum image size allowed is 3MB.');
          this.value = '';
          return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
          previewImg.src = e.target.result;
          previewImg.style.display = 'block';
          if (placeholderText) placeholderText.style.display = 'none';
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // 4. Contact Farmer Modal Handlers
  const openEnquiryBtn = document.getElementById('openEnquiryModalBtn');
  const enquiryModal = document.getElementById('enquiryModal');
  const closeEnquiryBtn = document.getElementById('closeEnquiryModalBtn');

  if (openEnquiryBtn && enquiryModal) {
    openEnquiryBtn.addEventListener('click', () => {
      enquiryModal.classList.add('active');
    });
  }

  if (closeEnquiryBtn && enquiryModal) {
    closeEnquiryBtn.addEventListener('click', () => {
      enquiryModal.classList.remove('active');
    });
  }

  if (enquiryModal) {
    enquiryModal.addEventListener('click', (e) => {
      if (e.target === enquiryModal) {
        enquiryModal.classList.remove('active');
      }
    });
  }

  // 5. Fast-Fill Demo Credentials on Login Page
  const demoButtons = document.querySelectorAll('.demo-pill');
  if (demoButtons.length > 0) {
    const emailInput = document.getElementById('loginEmail');
    const passwordInput = document.getElementById('loginPassword');

    demoButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const email = btn.getAttribute('data-email');
        const role = btn.getAttribute('data-role');
        if (emailInput && passwordInput) {
          emailInput.value = email;
          passwordInput.value = role + '123';
          // Visual highlight
          emailInput.style.backgroundColor = '#ecfdf5';
          passwordInput.style.backgroundColor = '#ecfdf5';
          setTimeout(() => {
            emailInput.style.backgroundColor = '';
            passwordInput.style.backgroundColor = '';
          }, 800);
        }
      });
    });
  }

  // 6. Confirmations for Critical Actions
  document.querySelectorAll('.confirm-delete').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!confirm('Are you sure you want to permanently delete this listing? This action cannot be undone.')) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll('.confirm-status-sold').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!confirm('Mark this produce as SOLD? This will indicate the harvest was successfully cleared.')) {
        e.preventDefault();
      }
    });
  });
});
