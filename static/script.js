// Navbar dropdown toggles (click-based)
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var dropdowns = document.querySelectorAll('.nav-dropdown');
    if (!dropdowns.length) return;

    dropdowns.forEach(function (dd) {
      var btn = dd.querySelector('.nav-drop-btn');
      if (!btn) return;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var wasOpen = dd.classList.contains('open');
        dropdowns.forEach(function (d) { d.classList.remove('open'); });
        if (!wasOpen) dd.classList.add('open');
      });
    });

    document.addEventListener('click', function () {
      dropdowns.forEach(function (d) { d.classList.remove('open'); });
    });

    // Auto-highlight active group based on current URL
    var path = window.location.pathname;
    var map = {
      '/report': 0, '/my-items': 0, '/matches': 0,
      '/my-claims': 1, '/notifications': 1,
      '/my-chats': 2, '/contact-admin': 2,
      '/profile': 3
    };
    var idx = map[path];
    if (idx !== undefined && dropdowns[idx]) {
      dropdowns[idx].classList.add('nav-active');
    }
  });
}());

// Image preview
document.addEventListener('DOMContentLoaded', function() {
  const imageInput = document.getElementById('image');
  if (imageInput) {
    imageInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = function(event) {
          const preview = document.getElementById('image-preview');
          if (preview) {
            preview.src = event.target.result;
            preview.style.display = 'block';
          }
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Auto-hide alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.display = 'none';
    }, 5000);
  });

  // Live Search & Filter functionality
  const searchBtn = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');
  const typeFilter = document.getElementById('type-filter');
  const categoryFilter = document.getElementById('category-filter');
  const itemsGrid = document.querySelector('.grid-3');

  function renderItems(items) {
    if (!itemsGrid) return;
    itemsGrid.innerHTML = '';
    if (items.length === 0) {
      itemsGrid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:2rem;color:#888;">No items found. Try adjusting your search filters.</div>';
      return;
    }
    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `
        ${item.image ? `<img src='/static/uploads/${item.image}' alt='${item.name}' class='card-image'>` : `<div style='width:100%;height:200px;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:3rem;'>📦</div>`}
        <div class='card-body'>
          <div style='display:flex;justify-content:space-between;align-items:start;margin-bottom:0.5rem;'>
            <h3 class='card-title'>${item.name}</h3>
            ${item.type === 'lost' ? `<span style='background:#fee2e2;color:#991b1b;padding:0.25rem 0.75rem;border-radius:0.25rem;font-size:0.8rem;font-weight:600;'>LOST</span>` : `<span style='background:#d1fae5;color:#065f46;padding:0.25rem 0.75rem;border-radius:0.25rem;font-size:0.8rem;font-weight:600;'>FOUND</span>`}
          </div>
          <p class='card-meta'>📂 ${item.category}</p>
          <p class='card-meta'>📍 ${item.location}</p>
          <p style='color:var(--text-muted);margin-bottom:1rem;'>${item.description ? item.description.substring(0,100) + (item.description.length > 100 ? '...' : '') : ''}</p>
          <p class='card-meta'>By: <strong>${item.reporter_name}</strong></p>
          <div style='display:flex;gap:0.5rem;margin-top:1rem;'>
            <a href='/item/${item.id}' class='btn btn-primary' style='flex:1;text-align:center;'>View Details</a>
          </div>
        </div>
      `;
      itemsGrid.appendChild(card);
    });
  }

  function fetchAndRenderItems() {
    const search = searchInput ? searchInput.value : '';
    const type = typeFilter ? typeFilter.value : '';
    const category = categoryFilter ? categoryFilter.value : '';
    let url = `/api/items?search=${encodeURIComponent(search)}&type=${encodeURIComponent(type)}&category=${encodeURIComponent(category)}`;
    fetch(url)
      .then(res => res.json())
      .then(data => renderItems(data));
  }

  if (searchBtn && searchInput && typeFilter && categoryFilter && itemsGrid) {
    searchBtn.addEventListener('click', function(e) {
      e.preventDefault();
      fetchAndRenderItems();
    });
    searchInput.addEventListener('input', fetchAndRenderItems);
    typeFilter.addEventListener('change', fetchAndRenderItems);
    categoryFilter.addEventListener('change', fetchAndRenderItems);
  }

  // Smooth scroll for navigation
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
});

// Validate form
function validateForm(formId) {
  const form = document.getElementById(formId);
  if (form) {
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;

    inputs.forEach(input => {
      if (!input.value.trim()) {
        input.style.borderColor = '#ef4444';
        isValid = false;
      } else {
        input.style.borderColor = '';
      }
    });

    return isValid;
  }
  return true;
}

// Confirm delete
function confirmDelete(message = 'Are you sure?') {
  return confirm(message);
}
