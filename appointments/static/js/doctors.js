/* Doctor directory: filter by department + live search, and profile modal. */
(function () {
  var chips = document.querySelectorAll('#deptChips [data-filter]');
  var items = document.querySelectorAll('.doctor-item');
  var search = document.getElementById('doctorSearch');
  var empty = document.getElementById('noDoctors');
  var count = document.getElementById('doctorCount');
  var grid = document.getElementById('doctorGrid');
  var activeDept = (grid && grid.getAttribute('data-initial-dept')) || 'ALL';

  function apply() {
    var term = (search.value || '').trim().toLowerCase();
    var shown = 0;
    items.forEach(function (item) {
      var deptOk = activeDept === 'ALL' || item.getAttribute('data-department') === activeDept;
      var textOk = !term || item.getAttribute('data-search').indexOf(term) !== -1;
      var visible = deptOk && textOk;
      item.classList.toggle('d-none', !visible);
      if (visible) { shown += 1; }
    });
    empty.classList.toggle('d-none', shown !== 0 || items.length === 0);
    count.textContent = items.length
      ? 'Showing ' + shown + ' of ' + items.length + ' doctor' + (items.length === 1 ? '' : 's')
      : '';
  }

  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      activeDept = chip.getAttribute('data-filter');
      chips.forEach(function (c) { c.classList.toggle('active', c === chip); });
      apply();
    });
  });
  if (search) { search.addEventListener('input', apply); }
  apply();

  // Fill the shared profile modal from the clicked button's data attributes.
  var modal = document.getElementById('doctorModal');
  if (modal) {
    modal.addEventListener('show.bs.modal', function (event) {
      var b = event.relatedTarget;
      if (!b) { return; }
      document.getElementById('doctorModalLabel').textContent = b.getAttribute('data-name');
      document.getElementById('mSpec').textContent = b.getAttribute('data-spec');
      document.getElementById('mBio').textContent = b.getAttribute('data-bio') || 'Profile details coming soon.';
      document.getElementById('mDept').textContent = b.getAttribute('data-dept');
      document.getElementById('mYears').textContent = b.getAttribute('data-years') + ' years';
      document.getElementById('mFee').textContent = '\u20B9' + b.getAttribute('data-fee');
      document.getElementById('mDays').textContent = b.getAttribute('data-days');
      document.getElementById('mBook').setAttribute('href', b.getAttribute('data-book'));
    });
  }
})();
