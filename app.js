const SHOPS = ['Colruyt', 'Lidl', 'Albert Heijn'];

const formatCurrency = (value) =>
  new Intl.NumberFormat('nl-BE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(value);

const normalizePrice = (product, shopPrice) => {
  if (shopPrice == null) return null;
  return shopPrice / product.quantity;
};

const toPackLabel = (product) => {
  if (product.unitType === 'unit') {
    return `${product.quantity} unit${product.quantity > 1 ? 's' : ''}`;
  }
  return `${product.quantity}${product.unitType}`;
};

const createRow = (product) => {
  const tr = document.createElement('tr');

  const normalized = SHOPS.map((shop) => {
    const value = product.prices[shop] ?? null;
    return { shop, packPrice: value, normalized: normalizePrice(product, value) };
  });

  const available = normalized.filter((entry) => entry.normalized != null);
  const best = available.sort((a, b) => a.normalized - b.normalized)[0];

  const cells = [];

  cells.push(`
    <td>
      <div class="product-title">${product.name}</div>
      <div class="product-meta">${product.category}</div>
    </td>
  `);

  cells.push(`<td>${toPackLabel(product)}</td>`);
  cells.push(`<td>${product.unitType === 'unit' ? 'per unit' : `per ${product.unitType}`}</td>`);

  for (const shopData of normalized) {
    if (shopData.packPrice == null) {
      cells.push('<td><span class="na">NA</span></td>');
      continue;
    }

    cells.push(`<td>${formatCurrency(shopData.normalized)}</td>`);
  }

  if (best) {
    cells.push(
      `<td><span class="badge best">${best.shop} · ${formatCurrency(best.normalized)}</span></td>`
    );
  } else {
    cells.push('<td><span class="na">No known price</span></td>');
  }

  tr.innerHTML = cells.join('');
  return tr;
};

const loadProducts = async () => {
  const response = await fetch(`data/prices.json?t=${Date.now()}`);
  return response.json();
};

const init = async () => {
  let products = await loadProducts();

  const searchInput = document.querySelector('#searchInput');
  const categorySelect = document.querySelector('#categorySelect');
  const tableBody = document.querySelector('#priceTableBody');
  const stats = document.querySelector('#stats');
  const refreshButton = document.querySelector('#refreshButton');
  const loadingIndicator = document.querySelector('#loadingIndicator');

  const fillCategories = () => {
    categorySelect.innerHTML = '<option value="all">All</option>';
    const categories = [...new Set(products.map((p) => p.category))].sort();
    categories.forEach((category) => {
      const option = document.createElement('option');
      option.value = category;
      option.textContent = category;
      categorySelect.appendChild(option);
    });
  };

  const render = () => {
    const search = searchInput.value.trim().toLowerCase();
    const category = categorySelect.value;

    const filtered = products.filter((p) => {
      const inCategory = category === 'all' || p.category === category;
      const searchable = `${p.name} ${p.category}`.toLowerCase();
      const inSearch = searchable.includes(search);
      return inCategory && inSearch;
    });

    tableBody.innerHTML = '';
    if (!filtered.length) {
      const noResults = document.querySelector('#noResultsTemplate').content.cloneNode(true);
      tableBody.appendChild(noResults);
    } else {
      filtered.forEach((product) => tableBody.appendChild(createRow(product)));
    }

    stats.textContent = `${filtered.length} / ${products.length} products shown`;
  };

  const setRefreshingState = (isRefreshing) => {
    refreshButton.disabled = isRefreshing;
    loadingIndicator.classList.toggle('hidden', !isRefreshing);
  };

  const refreshData = async () => {
    try {
      setRefreshingState(true);
      const minimumLoading = new Promise((resolve) => setTimeout(resolve, 800));
      const response = await fetch('/api/scrape', { method: 'POST' });
      if (!response.ok) {
        throw new Error('Failed to scrape');
      }
      const payload = await response.json();
      await minimumLoading;
      products = payload.products;
      fillCategories();
      render();
    } catch (error) {
      alert('Scraping failed. Run the project with `python server.py` and try again.');
    } finally {
      setRefreshingState(false);
    }
  };

  searchInput.addEventListener('input', render);
  categorySelect.addEventListener('change', render);
  refreshButton.addEventListener('click', refreshData);

  fillCategories();
  render();
};

init();
