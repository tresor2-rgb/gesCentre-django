document.addEventListener('DOMContentLoaded', function () {
  initTheme();
  initSidebar();
  initConfirmations();
  initAutoDismiss();
  initQuestionForm();
  initMathPalette();
  initQuizMathPalettes();
  initQuizTimer();
  initAttendanceBulk();
  initCredentialsClose();
});

/* ----------------------------------------------------------------- Theme */
var THEME_KEY = 'appcentre-theme';
var THEME_MODES = ['light', 'dark', 'system'];
var themeMedia = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

function getThemeMode() {
  try {
    var mode = localStorage.getItem(THEME_KEY);
    return THEME_MODES.indexOf(mode) !== -1 ? mode : 'light';
  } catch (error) {
    return 'light';
  }
}

function resolveTheme(mode) {
  if (mode === 'dark') return 'dark';
  if (mode === 'system' && themeMedia && themeMedia.matches) return 'dark';
  return 'light';
}

function themeLabel(mode) {
  if (mode === 'dark') return 'Sombre';
  if (mode === 'system') return 'Système';
  return 'Clair';
}

function themeIcon(mode) {
  if (mode === 'dark') return 'bi-moon-stars';
  if (mode === 'system') return 'bi-circle-half';
  return 'bi-sun';
}

function applyTheme(mode) {
  var resolved = resolveTheme(mode);
  var root = document.documentElement;
  root.setAttribute('data-theme-mode', mode);
  root.setAttribute('data-theme', resolved);
  root.setAttribute('data-bs-theme', resolved);
  root.style.colorScheme = resolved;

  var label = themeLabel(mode);
  var icon = 'bi ' + themeIcon(mode);

  document.querySelectorAll('[data-theme-indicator]').forEach(function (btn) {
    var glyph = btn.querySelector('i');
    if (glyph) glyph.className = icon;
    btn.title = 'Thème : ' + label;
    btn.setAttribute('aria-label', 'Thème : ' + label);
  });

  document.querySelectorAll('[data-theme-cycle]').forEach(function (btn) {
    var glyph = btn.querySelector('i');
    if (glyph) glyph.className = icon;
    var text = btn.querySelector('[data-theme-label]');
    if (text) text.textContent = 'Thème : ' + label;
    btn.title = 'Thème : ' + label;
    btn.setAttribute('aria-label', 'Thème : ' + label);
  });

  document.querySelectorAll('[data-theme-set]').forEach(function (btn) {
    btn.classList.toggle('active', btn.getAttribute('data-theme-set') === mode);
    btn.setAttribute('aria-pressed', btn.getAttribute('data-theme-set') === mode ? 'true' : 'false');
  });
}

function setThemeMode(mode) {
  try {
    localStorage.setItem(THEME_KEY, mode);
  } catch (error) {
    /* localStorage unavailable: theme still applies for this page */
  }
  applyTheme(mode);
}

function cycleThemeMode() {
  var current = getThemeMode();
  var next = THEME_MODES[(THEME_MODES.indexOf(current) + 1) % THEME_MODES.length];
  setThemeMode(next);
}

function initTheme() {
  applyTheme(getThemeMode());

  document.querySelectorAll('[data-theme-cycle]').forEach(function (btn) {
    btn.addEventListener('click', cycleThemeMode);
  });

  document.querySelectorAll('[data-theme-set]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setThemeMode(btn.getAttribute('data-theme-set'));
    });
  });

  if (themeMedia) {
    var onSystemThemeChange = function () {
      if (getThemeMode() === 'system') applyTheme('system');
    };
    if (themeMedia.addEventListener) {
      themeMedia.addEventListener('change', onSystemThemeChange);
    } else if (themeMedia.addListener) {
      themeMedia.addListener(onSystemThemeChange);
    }
  }
}

function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.querySelector('.sidebar-backdrop');
  if (!sidebar) return;

  document.querySelectorAll('[data-sidebar-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      sidebar.classList.add('open');
      if (backdrop) backdrop.classList.add('show');
    });
  });

  document.querySelectorAll('[data-sidebar-close]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('show');
    });
  });
}

function initConfirmations() {
  document.querySelectorAll('form[data-confirm], a[data-confirm], button[data-confirm]').forEach(function (el) {
    el.addEventListener(el.tagName === 'FORM' ? 'submit' : 'click', function (event) {
      if (!window.confirm(el.getAttribute('data-confirm'))) {
        event.preventDefault();
      }
    });
  });
}

function initAutoDismiss() {
  document.querySelectorAll('.app-alert').forEach(function (alert) {
    window.setTimeout(function () {
      if (window.bootstrap && bootstrap.Alert) {
        bootstrap.Alert.getOrCreateInstance(alert).close();
      } else {
        alert.remove();
      }
    }, 9000);
  });
}

function initCredentialsClose() {
  const btn = document.querySelector('[data-credentials-close]');
  if (!btn) return;
  btn.addEventListener('click', function () {
    const card = btn.closest('.credentials-card');
    if (card) card.remove();
  });
}

/* --------------------------------------------------------------- Quiz form */
function initQuestionForm() {
  const typeSelect = document.getElementById('id_question_type');
  if (!typeSelect) return;

  const sections = {
    qcm: document.getElementById('qcm-section'),
    true_false: document.getElementById('true-false-section'),
    short_answer: document.getElementById('short-answer-section'),
  };
  const optionRows = document.getElementById('option-rows');
  const addButton = document.getElementById('add-option');
  const countInput = document.getElementById('option_count');
  let optionCount = 0;

  function addOptionRow(text) {
    const index = optionCount;
    optionCount += 1;
    const row = document.createElement('div');
    row.className = 'option-row';
    row.innerHTML =
      '<input type="radio" class="form-check-input" name="correct_option" value="' + index + '" title="Bonne réponse">' +
      '<input type="text" class="form-control" name="option_text_' + index + '" placeholder="Option ' + (index + 1) + '" value="' + (text || '') + '">' +
      '<input type="file" class="form-control" name="option_image_' + index + '" accept="image/*" style="max-width:190px">' +
      '<button type="button" class="btn btn-outline-danger btn-sm remove-option" title="Supprimer"><i class="bi bi-trash"></i></button>';
    optionRows.appendChild(row);
    row.querySelector('.remove-option').addEventListener('click', function () {
      row.remove();
    });
    if (countInput) countInput.value = optionCount;
  }

  function ensureOptions() {
    if (!optionRows) return;
    if (optionRows.querySelectorAll('.option-row').length === 0) {
      addOptionRow('');
      addOptionRow('');
    }
  }

  function updateSections() {
    const value = typeSelect.value;
    Object.keys(sections).forEach(function (key) {
      if (!sections[key]) return;
      sections[key].style.display = key === value ? '' : 'none';
    });
    if (value === 'qcm') ensureOptions();
  }

  typeSelect.addEventListener('change', updateSections);
  if (addButton) {
    addButton.addEventListener('click', function () {
      addOptionRow('');
    });
  }
  updateSections();
}

function initMathPalette() {
  const checkbox = document.getElementById('id_enable_math_keyboard');
  const palette = document.getElementById('math-palette');
  if (!checkbox || !palette) return;

  let lastFocused = null;
  document.querySelectorAll('#question-form input[type="text"], #question-form textarea').forEach(function (input) {
    input.addEventListener('focus', function () { lastFocused = input; });
  });

  function togglePalette() {
    palette.style.display = checkbox.checked ? '' : 'none';
  }
  checkbox.addEventListener('change', togglePalette);
  togglePalette();

  palette.querySelectorAll('button[data-math]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const symbol = btn.getAttribute('data-math');
      const target = lastFocused || document.getElementById('id_question_text');
      if (!target) return;
      const start = target.selectionStart || 0;
      const end = target.selectionEnd || 0;
      const value = target.value || '';
      target.value = value.slice(0, start) + symbol + value.slice(end);
      target.focus();
      target.selectionStart = target.selectionEnd = start + symbol.length;
    });
  });
}

/* ----------------------------------------------------------------- Timer */
function initQuizMathPalettes() {
  document.querySelectorAll('[data-math-palette]').forEach(function (palette) {
    const block = palette.closest('[data-question-block]') || document;
    const input = block.querySelector('[data-math-input]');
    if (!input) return;

    palette.querySelectorAll('button[data-math]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const symbol = btn.getAttribute('data-math');
        const start = input.selectionStart || 0;
        const end = input.selectionEnd || 0;
        const value = input.value || '';
        input.value = value.slice(0, start) + symbol + value.slice(end);
        input.focus();
        input.selectionStart = input.selectionEnd = start + symbol.length;
      });
    });
  });
}

/* ----------------------------------------------------------------- Timer */
function initQuizTimer() {
  const timer = document.getElementById('quiz-timer');
  const form = document.getElementById('quiz-form');
  if (!timer) return;

  let seconds = parseInt(timer.getAttribute('data-seconds'), 10);
  if (isNaN(seconds) || seconds <= 0) return;

  function format(total) {
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) {
      return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }

  function render() {
    timer.querySelector('span').textContent = format(seconds);
    if (seconds <= 60) timer.classList.add('danger');
  }

  render();
  const interval = window.setInterval(function () {
    seconds -= 1;
    if (seconds <= 0) {
      window.clearInterval(interval);
      render();
      if (form) form.submit();
      return;
    }
    render();
  }, 1000);
}

/* ------------------------------------------------------------- Attendance */
function initAttendanceBulk() {
  document.querySelectorAll('[data-attendance-status]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const value = btn.getAttribute('data-attendance-status');
      document.querySelectorAll('select[data-attendance-select]').forEach(function (select) {
        select.value = value;
      });
    });
  });
}
