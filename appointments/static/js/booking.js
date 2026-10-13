/* Booking page: loads slots for the chosen doctor + date and lets the patient pick one.
   The server re-validates everything on submit, so this is a convenience, not a security check. */
(function () {
  var form = document.getElementById('bookingForm');
  if (!form) { return; }

  var doctorSel = document.getElementById('id_doctor');
  var dateInput = document.getElementById('id_date');
  var slotInput = document.getElementById('id_time_slot');
  var grid = document.getElementById('slotGrid');
  var message = document.getElementById('slotMessage');
  var summary = document.getElementById('bookingSummary');
  var url = form.getAttribute('data-slots-url');
  var defaultSummary = summary.textContent;
  var requestId = 0;

  function setMessage(text, isError) {
    message.textContent = text;
    message.classList.toggle('is-error', !!isError);
  }

  function choose(button, slot) {
    grid.querySelectorAll('.slot').forEach(function (b) {
      b.classList.remove('is-chosen');
      b.setAttribute('aria-pressed', 'false');
    });
    button.classList.add('is-chosen');
    button.setAttribute('aria-pressed', 'true');
    slotInput.value = slot.value;
    var doctorName = doctorSel.options[doctorSel.selectedIndex].text;
    summary.textContent = doctorName + ' \u00B7 ' + dateInput.value + ' \u00B7 ' + slot.label;
  }

  function render(slots) {
    grid.innerHTML = '';
    var previous = slotInput.value;
    var stillValid = false;
    slots.forEach(function (slot) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'slot is-' + slot.state;
      b.setAttribute('aria-pressed', 'false');
      b.textContent = slot.label;
      if (slot.state === 'booked') {
        var tag = document.createElement('small'); tag.textContent = 'Booked'; b.appendChild(tag);
        b.disabled = true;
      } else if (slot.state === 'past') {
        var tag2 = document.createElement('small'); tag2.textContent = 'Passed'; b.appendChild(tag2);
        b.disabled = true;
      } else {
        b.addEventListener('click', function () { choose(b, slot); });
        if (slot.value === previous) { stillValid = true; choose(b, slot); }
      }
      grid.appendChild(b);
    });
    if (!stillValid) { slotInput.value = ''; summary.textContent = defaultSummary; }
    var open = slots.filter(function (s) { return s.state === 'available'; }).length;
    setMessage(open ? open + ' open slot' + (open === 1 ? '' : 's') + '. Tap a time to select it.'
                    : 'No open slots left on this day. Try another date.', !open);
  }

  function load() {
    var doctor = doctorSel.value;
    var day = dateInput.value;
    grid.innerHTML = '';
    if (!doctor || !day) {
      slotInput.value = '';
      summary.textContent = defaultSummary;
      setMessage('Select a doctor and a date to see open times.');
      return;
    }
    var thisRequest = ++requestId;
    setMessage('Checking availability\u2026');
    fetch(url + '?doctor=' + encodeURIComponent(doctor) + '&date=' + encodeURIComponent(day), {
      headers: { 'Accept': 'application/json' }, credentials: 'same-origin'
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (thisRequest !== requestId) { return; }  // a newer request replaced this one
        if (!res.ok) { slotInput.value = ''; setMessage(res.data.error || 'Could not load slots.', true); return; }
        if (res.data.closed) { slotInput.value = ''; setMessage(res.data.message, true); return; }
        render(res.data.slots);
      })
      .catch(function () {
        if (thisRequest === requestId) { setMessage('Could not load slots. Check your connection and try again.', true); }
      });
  }

  doctorSel.addEventListener('change', load);
  dateInput.addEventListener('change', load);

  form.addEventListener('submit', function (e) {
    if (!slotInput.value) {
      e.preventDefault();
      setMessage('Please pick a time slot before submitting.', true);
      grid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });

  load();  // restores slots after a failed submit or when ?doctor= is preselected
})();
