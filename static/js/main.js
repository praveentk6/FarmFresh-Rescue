/**
 * FarmFresh Rescue - Client-side interactive enhancements
 * Includes:
 * 1. Mobile menu toggle & drawer
 * 2. Flash alert auto-dismiss & close
 * 3. Image upload preview with size validation
 * 4. Purchase order modal & live total calculation
 * 5. Tamil & English Voice-Based Product Listing assistant
 * 6. Live notifications badge polling
 * 7. Fast-fill demo credentials
 * 8. Confirmation dialogs for critical actions
 */

document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // 1. Mobile Menu Toggle & Navigation Drawer
  // ==========================================
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
        if (window.innerWidth <= 991) {
          navMenuWrapper.classList.remove('active');
          menuToggle.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
        }
      });
    });
  }

  // ==========================================
  // 1b. User Profile Dropdown Popover (Desktop, Laptop & Mobile)
  // ==========================================
  window.toggleUserProfileDropdown = function(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const btn = document.getElementById('userProfileBtn');
    if (btn) {
      btn.click();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const userProfileTrigger = document.getElementById('userProfileBtn');
  const userProfilePopover = document.getElementById('userProfilePopover');

  function repositionProfilePopover() {
    if (!userProfilePopover || !userProfilePopover.classList.contains('active')) return;
    userProfilePopover.style.left = '';
    userProfilePopover.style.right = '0px';

    const rect = userProfilePopover.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 12;

    // Check right edge boundary
    if (rect.right > viewportWidth - margin) {
      const rightOverflow = rect.right - (viewportWidth - margin);
      userProfilePopover.style.right = `${rightOverflow}px`;
    }

    // Check left edge boundary
    const updatedRect = userProfilePopover.getBoundingClientRect();
    if (updatedRect.left < margin) {
      const offsetNeeded = margin - updatedRect.left;
      const currentRight = parseFloat(userProfilePopover.style.right || '0');
      userProfilePopover.style.right = `${currentRight - offsetNeeded}px`;
    }

    // Check bottom viewport boundary
    if (updatedRect.bottom > viewportHeight - margin) {
      const maxHeight = viewportHeight - updatedRect.top - margin;
      if (maxHeight > 140) {
        userProfilePopover.style.maxHeight = `${maxHeight}px`;
        userProfilePopover.style.overflowY = 'auto';
      }
    }
  }

  if (userProfileTrigger && userProfilePopover) {
    userProfileTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      // If mobile hamburger nav is open, close it
      if (typeof navMenuWrapper !== 'undefined' && navMenuWrapper && navMenuWrapper.classList.contains('active')) {
        navMenuWrapper.classList.remove('active');
        if (typeof menuToggle !== 'undefined' && menuToggle) {
          menuToggle.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
        }
      }

      const isOpen = userProfilePopover.classList.contains('active');
      if (!isOpen) {
        userProfilePopover.classList.add('active');
        userProfileTrigger.setAttribute('aria-expanded', 'true');
        repositionProfilePopover();
      } else {
        userProfilePopover.classList.remove('active');
        userProfileTrigger.setAttribute('aria-expanded', 'false');
      }
    });

    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (!userProfilePopover.contains(e.target) && !userProfileTrigger.contains(e.target)) {
        userProfilePopover.classList.remove('active');
        userProfileTrigger.setAttribute('aria-expanded', 'false');
      }
    });

    // Close on selecting any option inside the dropdown
    userProfilePopover.querySelectorAll('a, button').forEach(item => {
      item.addEventListener('click', () => {
        userProfilePopover.classList.remove('active');
        userProfileTrigger.setAttribute('aria-expanded', 'false');
      });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && userProfilePopover.classList.contains('active')) {
        userProfilePopover.classList.remove('active');
        userProfileTrigger.setAttribute('aria-expanded', 'false');
        userProfileTrigger.focus();
      }
    });

    // Recalculate position on window resize
    window.addEventListener('resize', () => {
      if (userProfilePopover.classList.contains('active')) {
        repositionProfilePopover();
      }
    });
  }

  // ==========================================
  // 2. Auto-dismiss Flash Alerts after 5 seconds
  // ==========================================
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 500);
    }, 5500);
  });

  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');
      if (alert) alert.remove();
    });
  });

  // ==========================================
  // 3. Image Upload Live Preview
  // ==========================================
  const photoInput = document.getElementById('cropPhotoInput');
  const previewImg = document.getElementById('cropPhotoPreview');
  const previewContainer = document.getElementById('imagePreviewContainer');
  const placeholderText = document.getElementById('previewPlaceholderText');

  if (photoInput && previewImg) {
    photoInput.addEventListener('change', function () {
      const file = this.files[0];
      if (file) {
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

  // ==========================================
  // 4. Contact Farmer / Order Modal Handlers
  // ==========================================
  const openEnquiryBtn = document.getElementById('openEnquiryModalBtn');
  const enquiryModal = document.getElementById('enquiryModal');
  const closeEnquiryBtn = document.getElementById('closeEnquiryModalBtn');

  if (openEnquiryBtn && enquiryModal) {
    openEnquiryBtn.addEventListener('click', () => {
      enquiryModal.classList.add('active');
      recalcModalTotal();
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

  // Auto-open enquiry modal if URL hash is #enquiry-section
  // (Triggered by "Contact Farmer" button on the browse listings page)
  if (enquiryModal && window.location.hash === '#enquiry-section') {
    setTimeout(() => {
      enquiryModal.classList.add('active');
      recalcModalTotal();
      // Scroll to farmer contact section
      const contactCard = document.querySelector('.farmer-contact-card');
      if (contactCard) {
        contactCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 300);
  }

  // Live order total price recalculator
  const orderModalQty = document.getElementById('orderModalQty');
  const orderModalPrice = document.getElementById('orderModalPrice');
  const orderModalTotal = document.getElementById('orderModalTotal');

  function recalcModalTotal() {
    if (orderModalQty && orderModalPrice && orderModalTotal) {
      const qty = parseFloat(orderModalQty.value) || 0;
      const price = parseFloat(orderModalPrice.value) || 0;
      const total = qty * price;
      orderModalTotal.textContent = '₹' + Math.round(total).toLocaleString('en-IN');
    }
  }

  if (orderModalQty) orderModalQty.addEventListener('input', recalcModalTotal);
  if (orderModalPrice) orderModalPrice.addEventListener('input', recalcModalTotal);

  // ==========================================
  // 5. Tamil & English Voice-Based Product Listing
  // ==========================================
  const startVoiceBtn = document.getElementById('startVoiceBtn');
  const voiceBtnText = document.getElementById('voiceBtnText');
  const voiceStatusText = document.getElementById('voiceStatusText');
  const voiceTranscriptBox = document.getElementById('voiceTranscriptBox');
  const voiceTranscriptText = document.getElementById('voiceTranscriptText');
  const voiceErrorNotice = document.getElementById('voiceErrorNotice');
  const voiceErrorMsg = document.getElementById('voiceErrorMsg');
  const micIcon = document.getElementById('micIcon');

  const extractedCropChip = document.getElementById('extractedCropChip');
  const extractedQtyChip = document.getElementById('extractedQtyChip');
  const extractedPriceChip = document.getElementById('extractedPriceChip');

  // Form Fields
  const fieldCropName = document.getElementById('fieldCropName');
  const fieldQuantity = document.getElementById('fieldQuantity');
  const fieldPrice = document.getElementById('fieldPrice');
  const fieldCategory = document.getElementById('fieldCategory');

  if (startVoiceBtn) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      startVoiceBtn.addEventListener('click', () => {
        if (voiceErrorNotice && voiceErrorMsg) {
          voiceErrorNotice.style.display = 'block';
          voiceErrorMsg.textContent = 'Speech recognition is not supported in this browser. Please use Google Chrome, Microsoft Edge, or enter product details manually.';
        }
      });
    } else {
      let recognition = new SpeechRecognition();
      let isRecording = false;

      recognition.continuous = false;
      recognition.interimResults = false;

      function getSelectedVoiceLang() {
        const taRadio = document.getElementById('voiceLangTa');
        return (taRadio && taRadio.checked) ? 'ta-IN' : 'en-IN';
      }

      startVoiceBtn.addEventListener('click', () => {
        if (isRecording) {
          recognition.stop();
          return;
        }

        try {
          if (voiceErrorNotice) voiceErrorNotice.style.display = 'none';
          recognition.lang = getSelectedVoiceLang();
          recognition.start();
          isRecording = true;

          startVoiceBtn.classList.add('recording-pulse');
          if (voiceBtnText) voiceBtnText.textContent = 'கேட்கிறது... பேசவும் (Listening...)';
          if (voiceStatusText) voiceStatusText.textContent = 'Listening to your speech... Speak clearly near microphone.';
          if (micIcon) micIcon.textContent = '🔴';
        } catch (err) {
          console.error("Speech Recognition start error:", err);
        }
      });

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("Voice transcript received:", transcript);

        if (voiceTranscriptBox) voiceTranscriptBox.style.display = 'block';
        if (voiceTranscriptText) voiceTranscriptText.textContent = `"${transcript}"`;

        // Extract entities from speech
        parseVoiceListing(transcript, recognition.lang);
      };

      recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        if (voiceErrorNotice && voiceErrorMsg) {
          voiceErrorNotice.style.display = 'block';
          if (event.error === 'not-allowed') {
            voiceErrorMsg.textContent = 'Microphone access was denied. Please allow microphone permissions in your browser settings to use voice listing.';
          } else if (event.error === 'no-speech') {
            voiceErrorMsg.textContent = 'No speech was detected. Please click the button and speak into your microphone.';
          } else {
            voiceErrorMsg.textContent = 'Voice recognition error (' + event.error + '). You can fill the form fields manually.';
          }
        }
        resetVoiceUI();
      };

      recognition.onend = () => {
        resetVoiceUI();
      };

      function resetVoiceUI() {
        isRecording = false;
        if (startVoiceBtn) startVoiceBtn.classList.remove('recording-pulse');
        if (voiceBtnText) voiceBtnText.textContent = 'மீண்டும் பேச (Speak Again)';
        if (voiceStatusText) voiceStatusText.textContent = 'Speech recorded. Review fields below.';
        if (micIcon) micIcon.textContent = '🎙️';
      }
    }
  }

  /**
   * Agricultural Entity Extractor for Tamil and English
   */
  function parseVoiceListing(text, lang) {
    const lower = text.toLowerCase();
    let cropFound = null;
    let categoryFound = 'Vegetables';
    let qtyFound = null;
    let priceFound = null;

    // 1. Crop dictionary mapping (Tamil & English)
    const cropDict = [
      { names: ['தக்காளி', 'thakkali', 'tomato', 'tomatoes'], standard: 'Country Tomatoes (தக்காளி)', cat: 'Vegetables' },
      { names: ['வெங்காயம்', 'சின்ன வெங்காயம்', 'chinna vengayam', 'shallot', 'shallots', 'onion', 'onions', 'bellary'], standard: 'Small Onions / Shallots (சின்ன வெங்காயம்)', cat: 'Vegetables' },
      { names: ['கேரட்', 'carrot', 'carrots'], standard: 'Fresh Carrots (கேரட்)', cat: 'Vegetables' },
      { names: ['உருளைக்கிழங்கு', 'உருளை', 'potato', 'potatoes'], standard: 'Fresh Potatoes (உருளைக்கிழங்கு)', cat: 'Vegetables' },
      { names: ['கத்தரிக்காய்', 'கத்தரி', 'brinjal', 'eggplant'], standard: 'Brinjal / Eggplant (கத்தரிக்காய்)', cat: 'Vegetables' },
      { names: ['வெண்டைக்காய்', 'வெண்டை', 'okra', 'ladies finger'], standard: 'Ladies Finger / Okra (வெண்டைக்காய்)', cat: 'Vegetables' },
      { names: ['மிளகாய்', 'பச்சை மிளகாய்', 'chilli', 'green chilli'], standard: 'Green Chillies (பச்சை மிளகாய்)', cat: 'Spices & Herbs' },
      { names: ['முட்டைக்கோஸ்', 'கோஸ்', 'cabbage'], standard: 'Cabbage (முட்டைக்கோஸ்)', cat: 'Vegetables' },
      { names: ['காலிஃபிளவர்', 'cauliflower'], standard: 'Cauliflower (காலிஃபிளவர்)', cat: 'Vegetables' },
      { names: ['இஞ்சி', 'ginger'], standard: 'Hill Ginger (இஞ்சி)', cat: 'Spices & Herbs' },
      { names: ['பூண்டு', 'garlic'], standard: 'Garlic (பூண்டு)', cat: 'Spices & Herbs' },
      { names: ['தேங்காய்', 'இளநீர்', 'coconut', 'tender coconut', 'elaneer'], standard: 'Tender Coconuts (இளநீர்)', cat: 'Fruits' },
      { names: ['வாழைப்பழம்', 'வாழை', 'banana', 'bananas'], standard: 'Banana (வாழைப்பழம்)', cat: 'Fruits' },
      { names: ['மாம்பழம்', 'மாங்காய்', 'mango', 'mangoes'], standard: 'Mangoes (மாம்பழம்)', cat: 'Fruits' },
      { names: ['மல்லி', 'மல்லிகை', 'jasmine', 'malli', 'flowers'], standard: 'Madurai Jasmine Flowers (மல்லிகை)', cat: 'Flowers' },
      { names: ['கீரை', 'முருங்கை', 'drumstick', 'spinach', 'keerai'], standard: 'Fresh Greens / Keerai (கீரை)', cat: 'Vegetables' },
      { names: ['நெல்', 'அரிசி', 'paddy', 'rice', 'ponni'], standard: 'Ponni Rice / Paddy (நெல்)', cat: 'Grains & Pulses' }
    ];

    for (const item of cropDict) {
      for (const name of item.names) {
        if (lower.includes(name)) {
          cropFound = item.standard;
          categoryFound = item.cat;
          break;
        }
      }
      if (cropFound) break;
    }

    // 2. Quantity extraction (Tamil numbers & digits)
    // Examples: "100 கிலோ", "50 kg", "இருநூறு கிலோ", "நூறு கிலோ"
    const tamilNumMap = {
      'நூறு': 100, 'இருநூறு': 200, 'முந்நூறு': 300, 'நாநூறு': 400, 'ஐந்நூறு': 500,
      'ஆயிரம்': 1000, 'ஐம்பது': 50, 'இருபது': 20, 'முப்பது': 30, 'நாற்பது': 40
    };

    for (const [w, n] of Object.entries(tamilNumMap)) {
      if (lower.includes(w) && (lower.includes('கிலோ') || lower.includes('kg') || lower.includes('அளவு'))) {
        qtyFound = n;
        break;
      }
    }

    if (!qtyFound) {
      // Look for digit pattern followed by kg/கிலோ/டன்
      const qtyRegex = /(\d+(?:\.\d+)?)\s*(?:கிலோ|கிலோகிராம்|kg|kgs|quintal|டன்|qu|மூட்டை)/i;
      const match = lower.match(qtyRegex);
      if (match) {
        qtyFound = parseFloat(match[1]);
      } else {
        // Fallback: search for first number in speech
        const firstNum = lower.match(/(\d+(?:\.\d+)?)/);
        if (firstNum) {
          qtyFound = parseFloat(firstNum[1]);
        }
      }
    }

    // 3. Price extraction
    // Examples: "ஒரு கிலோ 15 ரூபாய்", "15 rs", "விலை 20", "ரூபாய் 15", "rate 25"
    const priceRegex = /(?:ரூபாய்|விலை|ரூ|rs|inr|price|rate|at)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:ரூபாய்|ரூ|rs|per\s*kg|\/\s*kg)/i;
    const priceMatch = lower.match(priceRegex);
    if (priceMatch) {
      priceFound = parseFloat(priceMatch[1] || priceMatch[2]);
    } else {
      // If we already found a qty, look for a second distinct number in string
      const allNums = [...lower.matchAll(/(\d+(?:\.\d+)?)/g)].map(m => parseFloat(m[1]));
      if (allNums.length >= 2 && qtyFound) {
        const remaining = allNums.filter(n => n !== qtyFound);
        if (remaining.length > 0) {
          priceFound = remaining[0];
        }
      }
    }

    // Populate Fields
    let filledCount = 0;

    if (cropFound && fieldCropName) {
      fieldCropName.value = cropFound;
      highlightField(fieldCropName);
      if (extractedCropChip) {
        extractedCropChip.style.display = 'inline-block';
        extractedCropChip.textContent = `Crop: ${cropFound}`;
      }
      if (fieldCategory) {
        fieldCategory.value = categoryFound;
      }
      filledCount++;
    }

    if (qtyFound && fieldQuantity) {
      fieldQuantity.value = qtyFound;
      highlightField(fieldQuantity);
      if (extractedQtyChip) {
        extractedQtyChip.style.display = 'inline-block';
        extractedQtyChip.textContent = `Quantity: ${qtyFound} kg`;
      }
      filledCount++;
    }

    if (priceFound && fieldPrice) {
      fieldPrice.value = priceFound;
      highlightField(fieldPrice);
      if (extractedPriceChip) {
        extractedPriceChip.style.display = 'inline-block';
        extractedPriceChip.textContent = `Price: ₹${priceFound}/kg`;
      }
      filledCount++;
    }

    if (filledCount === 0 && fieldCropName && !fieldCropName.value) {
      // Put whole raw text in crop name or description as fallback
      fieldCropName.value = text.slice(0, 60);
      highlightField(fieldCropName);
    }
  }

  function highlightField(elem) {
    elem.style.transition = 'background-color 0.4s ease, border-color 0.4s ease';
    elem.style.backgroundColor = '#ecfdf5';
    elem.style.borderColor = '#16a34a';
    setTimeout(() => {
      elem.style.backgroundColor = '';
      elem.style.borderColor = '';
    }, 1500);
  }

  // ==========================================
  // 6. Fast-Fill Demo Credentials on Login Page
  // ==========================================
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
          highlightField(emailInput);
          highlightField(passwordInput);
        }
      });
    });
  }

  // ==========================================
  // 7. Notification Unread Count Dynamic Poller
  // ==========================================
  function pollNotifications() {
    const badge = document.getElementById('notifBadge');
    if (!badge && !document.getElementById('navNotifBtn')) return;

    fetch('/api/notifications/unread-count')
      .then(res => res.json())
      .then(data => {
        if (data && typeof data.unread !== 'undefined') {
          const btn = document.getElementById('navNotifBtn');
          if (data.unread > 0) {
            if (badge) {
              badge.textContent = data.unread;
              badge.style.display = 'inline-block';
            } else if (btn) {
              const newBadge = document.createElement('span');
              newBadge.className = 'notif-badge';
              newBadge.id = 'notifBadge';
              newBadge.textContent = data.unread;
              btn.appendChild(newBadge);
            }
          } else if (badge) {
            badge.style.display = 'none';
          }
        }
      })
      .catch(err => {
        // Silent fail for polling
      });
  }

  // Poll notifications every 30 seconds
  setInterval(pollNotifications, 30000);

  // ==========================================
  // 8. Confirmations for Critical Actions
  // ==========================================
  document.querySelectorAll('.confirm-delete').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!confirm('Are you sure you want to permanently delete this listing? This action cannot be undone.')) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll('.confirm-status-sold').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!confirm('Mark this produce as SOLD? This will confirm the harvest was rescued from waste.')) {
        e.preventDefault();
      }
    });
  });

  // ==========================================
  // 9. FarmFresh AI 2.0 Floating Chatbot Widget
  // ==========================================
  const chatbotLauncher = document.getElementById('chatbotLauncher');
  const chatbotWindow = document.getElementById('chatbotWindow');
  const chatbotMinimizeBtn = document.getElementById('chatbotMinimizeBtn');
  const chatbotForm = document.getElementById('chatbotForm');
  const chatInput = document.getElementById('chatInput');
  const chatbotMessages = document.getElementById('chatbotMessages');
  const chatMicBtn = document.getElementById('chatMicBtn');
  const chatbotVoiceToggle = document.getElementById('chatbotVoiceToggle');
  const quickPills = document.querySelectorAll('.quick-pill');

  let isSpeechEnabled = false;

  if (chatbotLauncher && chatbotWindow) {
    chatbotLauncher.addEventListener('click', () => {
      const isHidden = chatbotWindow.style.display === 'none' || chatbotWindow.style.display === '';
      chatbotWindow.style.display = isHidden ? 'flex' : 'none';
      chatbotWindow.setAttribute('aria-hidden', String(!isHidden));
      if (isHidden && chatInput) chatInput.focus();
    });

    if (chatbotMinimizeBtn) {
      chatbotMinimizeBtn.addEventListener('click', () => {
        chatbotWindow.style.display = 'none';
        chatbotWindow.setAttribute('aria-hidden', 'true');
      });
    }

    if (chatbotVoiceToggle) {
      chatbotVoiceToggle.addEventListener('click', () => {
        isSpeechEnabled = !isSpeechEnabled;
        chatbotVoiceToggle.style.background = isSpeechEnabled ? '#16a34a' : 'rgba(255, 255, 255, 0.15)';
        chatbotVoiceToggle.title = isSpeechEnabled ? 'Spoken Responses ON' : 'Spoken Responses OFF';
      });
    }

    // Quick suggestions
    quickPills.forEach(pill => {
      pill.addEventListener('click', () => {
        const prompt = pill.getAttribute('data-prompt');
        if (prompt && chatInput) {
          chatInput.value = prompt;
          if (chatbotForm) {
            chatbotForm.dispatchEvent(new Event('submit', { cancelable: true }));
          }
        }
      });
    });

    // Chatbot Voice Input via Web Speech API
    if (chatMicBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const chatRec = new SpeechRecognition();
      chatRec.continuous = false;
      chatRec.interimResults = false;
      chatRec.lang = document.documentElement.lang === 'ta' ? 'ta-IN' : 'en-IN';

      chatMicBtn.addEventListener('click', () => {
        try {
          chatRec.start();
          chatMicBtn.classList.add('recording');
        } catch (e) {
          chatRec.stop();
          chatMicBtn.classList.remove('recording');
        }
      });

      chatRec.onresult = (evt) => {
        chatMicBtn.classList.remove('recording');
        const transcript = evt.results[0][0].transcript;
        if (transcript && chatInput) {
          chatInput.value = transcript;
          chatbotForm.dispatchEvent(new Event('submit', { cancelable: true }));
        }
      };

      chatRec.onerror = () => {
        chatMicBtn.classList.remove('recording');
      };

      chatRec.onend = () => {
        chatMicBtn.classList.remove('recording');
      };
    }

    // Chat form submit
    if (chatbotForm && chatInput && chatbotMessages) {
      chatbotForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        // Append user bubble
        appendChatMessage('user', text);
        chatInput.value = '';

        // Add loading bubble
        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-msg bot-msg';
        loadingDiv.id = loadingId;
        loadingDiv.innerHTML = '<div class="msg-bubble" style="color: #64748b; font-style: italic;">🌱 சிந்திக்கிறது / Analyzing...</div>';
        chatbotMessages.appendChild(loadingDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

        // Send to backend
        fetch('/api/ai/chatbot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        })
          .then(res => res.json())
          .then(data => {
            const el = document.getElementById(loadingId);
            if (el) el.remove();

            const reply = data.reply || 'மன்னிக்கவும், தகவலைப் பெறுவதில் தாமதம் ஏற்பட்டுள்ளது.';
            appendChatMessage('bot', reply);

            // Spoken voice reply if enabled
            if (isSpeechEnabled && 'speechSynthesis' in window) {
              const utter = new SpeechSynthesisUtterance(reply.replace(/[#*`_]/g, ''));
              utter.lang = (data.detected_lang === 'ta' || /[அ-ஹ]/.test(reply)) ? 'ta-IN' : 'en-IN';
              window.speechSynthesis.speak(utter);
            }
          })
          .catch(err => {
            const el = document.getElementById(loadingId);
            if (el) el.remove();
            appendChatMessage('bot', '⚠️ Connection error. Please try again.');
          });
      });
    }

    function appendChatMessage(role, text) {
      const div = document.createElement('div');
      div.className = `chat-msg ${role}-msg`;
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      div.innerHTML = `
        <div class="msg-bubble">${escapeHtml(text)}</div>
        <span class="msg-time">${timeStr}</span>
      `;
      chatbotMessages.appendChild(div);
      chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function escapeHtml(str) {
      return str.replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\n/g, '<br>');
    }
  }

  // ==========================================
  // 10. AI Smart Price Recommendation in Add Listing
  // ==========================================
  const btnAiPrice = document.getElementById('btnAiPrice');
  const aiPricePanel = document.getElementById('aiPricePanel');
  const btnApplyAiPrice = document.getElementById('btnApplyAiPrice');
  const fieldHarvestDate = document.getElementById('fieldHarvestDate');
  const fieldStorage = document.getElementById('fieldStorageCondition');

  if (btnAiPrice && aiPricePanel) {
    btnAiPrice.addEventListener('click', () => {
      const crop = fieldCropName ? fieldCropName.value.trim() : '';
      const qty = fieldQuantity ? fieldQuantity.value.trim() : 100;
      const hDate = fieldHarvestDate ? fieldHarvestDate.value.trim() : '';
      const storage = fieldStorage ? fieldStorage.value : 'ambient';
      const askPrice = fieldPrice ? fieldPrice.value.trim() : '';

      if (!crop) {
        alert('தயவுசெய்து விளைபொருள் பெயரை உள்ளிடவும் (Please enter a produce name first).');
        if (fieldCropName) fieldCropName.focus();
        return;
      }

      btnAiPrice.innerText = '⏳ கணக்கிடுகிறது...';
      btnAiPrice.disabled = true;

      fetch('/api/ai/price-recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          crop_name: crop,
          quantity: qty,
          harvest_date: hDate,
          storage_condition: storage,
          asking_price: askPrice
        })
      })
        .then(res => res.json())
        .then(data => {
          btnAiPrice.innerHTML = '<span>🤖</span> AI விலை';
          btnAiPrice.disabled = false;

          if (data.success && data.recommendation) {
            const rec = data.recommendation;
            aiPricePanel.style.display = 'block';

            const recEl = document.getElementById('aiRecPrice');
            const mktEl = document.getElementById('aiMktPrice');
            const revEl = document.getElementById('aiEstRevenue');
            const ratEl = document.getElementById('aiPriceRationale');

            if (recEl) recEl.innerText = '₹' + rec.suggested_price;
            if (mktEl) mktEl.innerText = '₹' + rec.mandi_benchmark;
            if (revEl) revEl.innerText = '₹' + Number(rec.expected_revenue || 0).toLocaleString();
            if (ratEl) ratEl.innerText = rec.rationale || 'Recommendation based on wholesale Mandi benchmarks and freshness.';

            if (btnApplyAiPrice) {
              btnApplyAiPrice.onclick = () => {
                if (fieldPrice) {
                  fieldPrice.value = rec.suggested_price;
                  highlightField(fieldPrice);
                }
                aiPricePanel.style.borderColor = '#16a34a';
              };
            }
          }
        })
        .catch(err => {
          btnAiPrice.innerHTML = '<span>🤖</span> AI விலை';
          btnAiPrice.disabled = false;
          alert('AI price recommendation service unavailable. Please enter price manually.');
        });
    });
  }

});
