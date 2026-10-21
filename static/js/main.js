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
        if (window.innerWidth <= 768) {
          navMenuWrapper.classList.remove('active');
          menuToggle.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
        }
      });
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

});
