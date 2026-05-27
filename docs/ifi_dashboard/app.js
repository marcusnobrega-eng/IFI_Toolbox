const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const METRICS = [
  { key: 'n_events', label: 'Frequency', short: 'Frequency', unit: 'events', icon: 'activity', type: 'numeric', palette: ['#fff7bc', '#fee391', '#fec44f', '#fe9929', '#ec7014', '#b24203'] },
  { key: 'p95_hazard_score', label: 'P95 hazard', short: 'Hazard', unit: '0-100', icon: 'gauge', type: 'numeric', palette: ['#edf8fb', '#bfd3e6', '#9ebcda', '#8c96c6', '#8856a7', '#4d1d80'] },
  { key: 'hotspot_score', label: 'Hotspots', short: 'Hotspots', unit: 'class', icon: 'flame', type: 'bivariate' },
  { key: 'dominant_cause', label: 'Dominant cause', short: 'Causes', unit: 'category', icon: 'layers', type: 'category' },
  { key: 'fatalities_apportioned_sum', label: 'Fatalities', short: 'Fatalities', unit: 'people', icon: 'heart-pulse', type: 'numeric', palette: ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#de2d26', '#8f1612'] },
  { key: 'crop_area_km2_apportioned_sum', label: 'Crop area', short: 'Crop', unit: 'km2', icon: 'wheat', type: 'numeric', palette: ['#f7fcf5', '#d9f0d3', '#addd8e', '#78c679', '#31a354', '#006837'] },
  { key: 'loss_2026_usd_apportioned_sum', label: 'Loss', short: 'Loss USD', unit: '2026 USD', icon: 'landmark', type: 'numeric', palette: ['#f7fbff', '#d0e1f2', '#9ecae1', '#6baed6', '#3182bd', '#08519c'] },
  { key: 'priority_score', label: 'Planning priority', short: 'Priority', unit: '0-100', icon: 'target', type: 'numeric', palette: ['#f7fcf0', '#e0f3db', '#ccebc5', '#a8ddb5', '#43a2ca', '#0868ac'] },
];

const BIVAR_COLORS = {
  '0-0': '#e8e8e8',
  '1-0': '#ace4e4',
  '2-0': '#5ac8c8',
  '0-1': '#dfb0d6',
  '1-1': '#a5add3',
  '2-1': '#5698b9',
  '0-2': '#be64ac',
  '1-2': '#8c62aa',
  '2-2': '#3b4994',
};

const appState = {
  analytics: null,
  geojson: null,
  features: [],
  featuresByGid: {},
  layerByGid: {},
  filteredFeatures: [],
  selectedGid: null,
  metric: 'n_events',
  filters: {
    search: '',
    state: 'all',
    cause: 'all',
    minEvents: 0,
    minHazard: 0,
    hotspotsOnly: false,
  },
  breaks: {},
  charts: {},
  map: null,
  districtLayer: null,
};

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function numberValue(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function fmt(value, digits = 0) {
  const n = numberValue(value);
  if (n === null) return '-';
  return n.toLocaleString('en-IN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function fmtCompact(value, digits = 1) {
  const n = numberValue(value);
  if (n === null) return '-';
  return new Intl.NumberFormat('en-US', {
    notation: Math.abs(n) >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: digits,
  }).format(n);
}

function fmtUsd(value) {
  const n = numberValue(value);
  if (n === null) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: Math.abs(n) >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(n) >= 100000 ? 1 : 0,
  }).format(n);
}

function fmtYear(value) {
  const n = numberValue(value);
  return n === null ? '-' : String(Math.round(n));
}

function fmtPercent(value, digits = 0) {
  const n = numberValue(value);
  if (n === null) return '-';
  return `${fmt(n * 100, digits)}%`;
}

function setText(id, value) {
  const node = byId(id);
  if (node) node.textContent = value;
}

function metricConfig(key = appState.metric) {
  return METRICS.find((metric) => metric.key === key) || METRICS[0];
}

function formatMetricValue(key, value) {
  const n = numberValue(value);
  if (n === null) return '-';
  if (key === 'loss_2026_usd_apportioned_sum') return fmtUsd(n);
  if (key === 'crop_area_km2_apportioned_sum') return `${fmtCompact(n, 1)} km2`;
  if (key === 'fatalities_apportioned_sum') return fmtCompact(n, 1);
  if (key === 'p95_hazard_score' || key === 'priority_score') return fmt(n, 1);
  if (key === 'hotspot_score') return n > 0 ? fmt(n, 0) : '-';
  return fmt(n, 0);
}

function chartTextColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--muted').trim() || '#63716d';
}

function chartGridColor() {
  return 'rgba(18, 33, 29, 0.09)';
}

function destroyChart(id) {
  if (appState.charts[id]) {
    appState.charts[id].destroy();
    delete appState.charts[id];
  }
}

function makeChart(id, config) {
  destroyChart(id);
  const node = byId(id);
  if (!node) return null;
  appState.charts[id] = new Chart(node, config);
  return appState.charts[id];
}

function baseChartOptions(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    resizeDelay: 100,
    animation: false,
    plugins: {
      legend: {
        labels: {
          color: chartTextColor(),
          boxWidth: 12,
          boxHeight: 12,
          usePointStyle: true,
        },
      },
      tooltip: {
        intersect: false,
        mode: 'nearest',
      },
    },
    scales: {
      x: {
        ticks: { color: chartTextColor(), maxTicksLimit: 8 },
        grid: { color: chartGridColor() },
      },
      y: {
        beginAtZero: true,
        ticks: { color: chartTextColor() },
        grid: { color: chartGridColor() },
      },
    },
    ...extra,
  };
}

function quantile(sortedValues, q) {
  if (!sortedValues.length) return 0;
  const pos = (sortedValues.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sortedValues[base + 1];
  return next === undefined ? sortedValues[base] : sortedValues[base] + rest * (next - sortedValues[base]);
}

function getBreaks(key) {
  if (appState.breaks[key]) return appState.breaks[key];
  const values = appState.features
    .map((feature) => numberValue(feature.properties[key]))
    .filter((value) => value !== null && value > 0)
    .sort((a, b) => a - b);
  if (!values.length) {
    appState.breaks[key] = [0, 1, 2, 3, 4, 5];
    return appState.breaks[key];
  }
  const breaks = [0, 0.2, 0.4, 0.6, 0.8, 0.95].map((q) => quantile(values, q));
  breaks.push(values[values.length - 1]);
  appState.breaks[key] = Array.from(new Set(breaks.map((value) => Number(value.toFixed(3)))));
  return appState.breaks[key];
}

function numericColor(key, value) {
  const config = metricConfig(key);
  const n = numberValue(value);
  if (n === null || n <= 0) return '#edf0f2';
  const palette = config.palette || METRICS[0].palette;
  const breaks = getBreaks(key);
  let index = 0;
  for (let i = 1; i < breaks.length; i += 1) {
    if (n > breaks[i]) index = i;
  }
  return palette[Math.min(index, palette.length - 1)];
}

function featureColor(feature) {
  const props = feature.properties;
  const config = metricConfig();
  if (config.type === 'category') {
    return appState.analytics.cause_palette[props.dominant_cause] || '#9aa4ad';
  }
  if (config.type === 'bivariate') {
    const freq = numberValue(props.freq_class);
    const sev = numberValue(props.severity_class);
    if (freq === null || sev === null || props.n_events <= 0) return '#edf0f2';
    return BIVAR_COLORS[`${Math.round(freq)}-${Math.round(sev)}`] || '#edf0f2';
  }
  return numericColor(config.key, props[config.key]);
}

function featureSearchText(props) {
  return [props.district, props.state, props.gid, props.dominant_cause].filter(Boolean).join(' ').toLowerCase();
}

function featureMatches(feature) {
  const props = feature.properties;
  const search = appState.filters.search.trim().toLowerCase();
  if (search && !featureSearchText(props).includes(search)) return false;
  if (appState.filters.state !== 'all' && props.state !== appState.filters.state) return false;
  if (appState.filters.cause !== 'all' && props.dominant_cause !== appState.filters.cause) return false;
  if ((numberValue(props.n_events) || 0) < appState.filters.minEvents) return false;
  if ((numberValue(props.p95_hazard_score) || 0) < appState.filters.minHazard) return false;
  if (appState.filters.hotspotsOnly && (numberValue(props.hotspot_score) || 0) < 6) return false;
  return true;
}

function styleFeature(feature) {
  const matched = featureMatches(feature);
  const selected = feature.properties.gid === appState.selectedGid;
  return {
    color: selected ? '#12211d' : 'rgba(255,255,255,0.92)',
    weight: selected ? 1.8 : 0.45,
    opacity: selected ? 1 : 0.9,
    fillColor: featureColor(feature),
    fillOpacity: matched ? 0.86 : 0.12,
  };
}

function renderMetricButtons() {
  const wrap = byId('metricButtons');
  wrap.innerHTML = METRICS.map((metric) => `
    <button type="button" data-metric="${metric.key}" class="${metric.key === appState.metric ? 'active' : ''}">
      <i data-lucide="${metric.icon}" aria-hidden="true"></i>
      <span>${escapeHtml(metric.short)}</span>
    </button>
  `).join('');
  wrap.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      appState.metric = button.dataset.metric;
      renderMetricButtons();
      refreshMap();
      renderDistrictList();
      renderLegend();
    });
  });
  if (window.lucide) lucide.createIcons();
}

function populateFilters() {
  const stateFilter = byId('stateFilter');
  const causeFilter = byId('causeFilter');
  appState.analytics.state_summary
    .map((row) => row.state)
    .sort((a, b) => a.localeCompare(b))
    .forEach((stateName) => {
      const option = document.createElement('option');
      option.value = stateName;
      option.textContent = stateName;
      stateFilter.appendChild(option);
    });

  appState.analytics.cause_summary.forEach((row) => {
    const option = document.createElement('option');
    option.value = row.cause;
    option.textContent = row.cause;
    causeFilter.appendChild(option);
  });

  byId('districtSearch').addEventListener('input', (event) => {
    appState.filters.search = event.target.value;
    refreshFilters();
  });
  stateFilter.addEventListener('change', (event) => {
    appState.filters.state = event.target.value;
    refreshFilters();
  });
  causeFilter.addEventListener('change', (event) => {
    appState.filters.cause = event.target.value;
    refreshFilters();
  });
  byId('minEventsFilter').addEventListener('input', (event) => {
    appState.filters.minEvents = Number(event.target.value) || 0;
    refreshFilters();
  });
  byId('minHazardFilter').addEventListener('input', (event) => {
    appState.filters.minHazard = Number(event.target.value) || 0;
    refreshFilters();
  });
  byId('hotspotFilter').addEventListener('change', (event) => {
    appState.filters.hotspotsOnly = event.target.checked;
    refreshFilters();
  });
}

function refreshFilters() {
  refreshMap();
  renderDistrictList();
}

function initMap() {
  appState.map = L.map('map', {
    preferCanvas: true,
    zoomControl: false,
  }).setView([22.7, 79.2], 5);
  L.control.zoom({ position: 'bottomright' }).addTo(appState.map);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 18,
  }).addTo(appState.map);

  appState.districtLayer = L.geoJSON(appState.geojson, {
    style: styleFeature,
    onEachFeature: (feature, layer) => {
      const props = feature.properties;
      appState.layerByGid[props.gid] = layer;
      layer.bindTooltip(
        `<strong>${escapeHtml(props.district)}</strong><br>${escapeHtml(props.state)}<br>${fmt(props.n_events)} events | P95 ${fmt(props.p95_hazard_score, 1)}`,
        { sticky: true }
      );
      layer.on('click', () => selectDistrict(props.gid, true));
      layer.on('mouseover', () => {
        if (props.gid !== appState.selectedGid) layer.setStyle({ weight: 1.2, color: '#12211d' });
      });
      layer.on('mouseout', () => {
        layer.setStyle(styleFeature(feature));
      });
    },
  }).addTo(appState.map);

  byId('fitAllButton').addEventListener('click', () => {
    appState.map.fitBounds(appState.districtLayer.getBounds(), { padding: [18, 18] });
  });
}

function refreshMap() {
  if (!appState.districtLayer) return;
  appState.districtLayer.eachLayer((layer) => {
    layer.setStyle(styleFeature(layer.feature));
    if (layer.feature.properties.gid === appState.selectedGid) layer.bringToFront();
  });
}

function renderLegend() {
  const config = metricConfig();
  setText('metricCaption', config.label);
  setText('legendTitle', config.label);
  setText('legendUnit', config.unit);
  const wrap = byId('legendItems');
  wrap.innerHTML = '';

  if (config.type === 'category') {
    appState.analytics.cause_summary.forEach((row) => {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="legend-row">
          <span class="legend-swatch" style="background:${appState.analytics.cause_palette[row.cause] || '#9aa4ad'}"></span>
          <span>${escapeHtml(row.cause)}</span>
          <strong>${fmt(row.n_event_district_records)}</strong>
        </div>
      `);
    });
    wrap.insertAdjacentHTML('beforeend', `
      <div class="legend-row">
        <span class="legend-swatch" style="background:${appState.analytics.cause_palette['No IFI record']}"></span>
        <span>No IFI record</span>
        <strong></strong>
      </div>
    `);
    return;
  }

  if (config.type === 'bivariate') {
    [
      ['0-0', 'Low frequency, low severity'],
      ['1-0', 'Medium frequency, low severity'],
      ['2-0', 'High frequency, low severity'],
      ['0-1', 'Low frequency, medium severity'],
      ['1-1', 'Medium frequency, medium severity'],
      ['2-1', 'High frequency, medium severity'],
      ['0-2', 'Low frequency, high severity'],
      ['1-2', 'Medium frequency, high severity'],
      ['2-2', 'High frequency, high severity'],
    ].forEach(([key, label]) => {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="legend-row">
          <span class="legend-swatch" style="background:${BIVAR_COLORS[key]}"></span>
          <span>${label}</span>
          <strong></strong>
        </div>
      `);
    });
    return;
  }

  const breaks = getBreaks(config.key);
  const palette = config.palette || METRICS[0].palette;
  for (let i = 0; i < palette.length; i += 1) {
    const from = breaks[i] ?? breaks[breaks.length - 1];
    const to = breaks[i + 1] ?? breaks[breaks.length - 1];
    const label = i === 0 ? `0-${formatMetricValue(config.key, to)}` : `${formatMetricValue(config.key, from)}-${formatMetricValue(config.key, to)}`;
    wrap.insertAdjacentHTML('beforeend', `
      <div class="legend-row">
        <span class="legend-swatch" style="background:${palette[i]}"></span>
        <span>${label}</span>
        <strong></strong>
      </div>
    `);
  }
}

function sortScore(props) {
  const config = metricConfig();
  if (config.type === 'category' || config.type === 'bivariate') return numberValue(props.n_events) || 0;
  return numberValue(props[config.key]) || 0;
}

function renderDistrictList() {
  const list = byId('districtList');
  const filtered = appState.features
    .filter(featureMatches)
    .sort((a, b) => sortScore(b.properties) - sortScore(a.properties) || a.properties.district.localeCompare(b.properties.district));
  appState.filteredFeatures = filtered;
  setText('visibleCount', `${fmt(filtered.length)} visible`);

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state">No districts match the active filters.</div>';
    return;
  }

  list.innerHTML = filtered.slice(0, 90).map((feature) => {
    const props = feature.properties;
    const value = metricConfig().type === 'category' ? props.dominant_cause : formatMetricValue(appState.metric, props[appState.metric]);
    return `
      <button class="district-item ${props.gid === appState.selectedGid ? 'active' : ''}" type="button" data-gid="${escapeHtml(props.gid)}">
        <span>
          <strong>${escapeHtml(props.district)}</strong>
          <span>${escapeHtml(props.state)} | ${fmt(props.n_events)} events | ${escapeHtml(props.dominant_cause)}</span>
        </span>
        <span class="district-score">${escapeHtml(value)}</span>
      </button>
    `;
  }).join('');

  list.querySelectorAll('.district-item').forEach((button) => {
    button.addEventListener('click', () => selectDistrict(button.dataset.gid, true));
  });
}

function renderMetadata(containerId, items) {
  const node = byId(containerId);
  node.innerHTML = items.map((item) => `
    <div>
      <dt>${escapeHtml(item.label)}</dt>
      <dd>${escapeHtml(item.value)}</dd>
    </div>
  `).join('');
}

function renderKpis(containerId, items) {
  const node = byId(containerId);
  node.innerHTML = items.map((item) => `
    <article>
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
    </article>
  `).join('');
}

function selectedProps() {
  const feature = appState.featuresByGid[appState.selectedGid];
  return feature ? feature.properties : null;
}

function selectDistrict(gid, panToDistrict = false) {
  if (!appState.featuresByGid[gid]) return;
  appState.selectedGid = gid;
  const props = selectedProps();
  setText('selectedEyebrow', props.dominant_cause);
  setText('selectedTitle', props.district);
  setText('selectedSubtitle', `${props.state} | ${fmtYear(props.first_year)}-${fmtYear(props.last_year)}`);
  setText('selectedEvents', fmt(props.n_events));
  setText('selectedHazard', fmt(props.p95_hazard_score, 1));
  setText('selectedPriority', fmt(props.priority_score, 1));

  refreshMap();
  renderDistrictList();
  renderDistrictPanel();

  const layer = appState.layerByGid[gid];
  if (panToDistrict && layer) {
    appState.map.fitBounds(layer.getBounds(), { padding: [32, 32], maxZoom: 8 });
  }
}

function renderDistrictPanel() {
  const props = selectedProps();
  if (!props) return;
  const detail = appState.analytics.district_details[props.gid] || {};

  setText('districtHeading', props.district);
  setText('districtState', props.state);
  setText('districtYearRange', `${fmtYear(props.first_year)}-${fmtYear(props.last_year)}`);
  setText('districtCauseTotal', `${fmt(props.n_events)} events`);
  setText('districtEventCount', `${fmt(props.n_events)} events`);

  renderMetadata('districtMetadata', [
    { label: 'GADM district ID', value: props.gid },
    { label: 'Dominant cause', value: props.dominant_cause },
    { label: 'Cause share', value: fmtPercent(props.dominant_cause_share, 0) },
    { label: 'High-confidence share', value: fmtPercent(props.high_confidence_share, 0) },
    { label: 'Event rank', value: `#${fmt(props.event_rank)}` },
    { label: 'Hazard rank', value: `#${fmt(props.hazard_rank)}` },
  ]);

  renderKpis('districtImpacts', [
    { label: 'Mapped events', value: fmt(props.n_events) },
    { label: 'P95 hazard', value: fmt(props.p95_hazard_score, 1) },
    { label: 'Fatalities', value: fmtCompact(props.fatalities_apportioned_sum, 1) },
    { label: 'People affected', value: fmtCompact(props.people_affected_apportioned_sum, 1) },
    { label: 'Crop area', value: `${fmtCompact(props.crop_area_km2_apportioned_sum, 1)} km2` },
    { label: 'Loss, 2026 USD', value: fmtUsd(props.loss_2026_usd_apportioned_sum) },
  ]);

  renderDistrictCharts(detail);
  renderEventTable(detail.top_events || []);
}

function renderDistrictCharts(detail) {
  const years = detail.year_counts || [];
  makeChart('districtYearChart', {
    type: 'line',
    data: {
      labels: years.map((row) => row.year),
      datasets: [
        {
          label: 'Events',
          data: years.map((row) => row.n_events),
          borderColor: '#137a68',
          backgroundColor: 'rgba(19,122,104,0.18)',
          fill: true,
          tension: 0.25,
          pointRadius: 1.8,
          yAxisID: 'y',
        },
        {
          label: 'Mean hazard',
          data: years.map((row) => row.mean_hazard_score),
          borderColor: '#c88719',
          backgroundColor: '#c88719',
          tension: 0.25,
          pointRadius: 1.6,
          yAxisID: 'y1',
        },
      ],
    },
    options: baseChartOptions({
      scales: {
        x: { ticks: { color: chartTextColor(), maxTicksLimit: 7 }, grid: { color: chartGridColor() } },
        y: { beginAtZero: true, ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y1: {
          position: 'right',
          beginAtZero: true,
          max: 100,
          ticks: { color: chartTextColor() },
          grid: { drawOnChartArea: false },
        },
      },
    }),
  });

  makeChart('districtMonthChart', {
    type: 'bar',
    data: {
      labels: MONTHS,
      datasets: [{
        label: 'Events',
        data: detail.month_counts || new Array(12).fill(0),
        backgroundColor: '#2f80ed',
        borderRadius: 4,
      }],
    },
    options: baseChartOptions({ plugins: { legend: { display: false } } }),
  });

  const causeEntries = Object.entries(detail.cause_counts || {}).sort((a, b) => b[1] - a[1]);
  makeChart('districtCauseChart', {
    type: 'doughnut',
    data: {
      labels: causeEntries.map(([cause]) => cause),
      datasets: [{
        data: causeEntries.map(([, value]) => value),
        backgroundColor: causeEntries.map(([cause]) => appState.analytics.cause_palette[cause] || '#9aa4ad'),
        borderColor: '#ffffff',
        borderWidth: 2,
      }],
    },
    options: baseChartOptions({
      cutout: '62%',
      scales: {},
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: chartTextColor(), boxWidth: 10, boxHeight: 10 },
        },
      },
    }),
  });
}

function renderEventTable(events) {
  const body = byId('eventTable');
  if (!events.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">No district-linked events.</td></tr>';
    return;
  }
  body.innerHTML = events.map((event) => `
    <tr>
      <td>
        <strong>${escapeHtml(event.uei)}</strong><br>
        <span>${escapeHtml(event.location || event.severity || '-')}</span>
      </td>
      <td>${fmtYear(event.year)}</td>
      <td>${escapeHtml(event.cause)}</td>
      <td class="numeric">${fmt(event.hazard_score, 1)}</td>
      <td class="numeric">${fmt(event.duration_days, 1)}</td>
    </tr>
  `).join('');
}

function renderGlobalStats() {
  const totals = appState.analytics.totals;
  setText('totalEvents', fmt(totals.unique_events_mapped));
  setText('totalDistricts', `${fmt(totals.districts_with_records)}/${fmt(totals.districts_total)}`);
  setText('totalRecords', fmt(totals.valid_event_district_records));
  setText('yearSpan', `${totals.year_start}-${totals.year_end}`);
  const generated = appState.analytics.metadata.generated_at.slice(0, 10);
  setText('assetStamp', `Updated ${generated} | ${totals.year_start}-${totals.year_end}`);
}

function renderIndiaPanel() {
  const totals = appState.analytics.totals;
  renderKpis('indiaKpis', [
    { label: 'Mapped events', value: fmt(totals.unique_events_mapped) },
    { label: 'Event-district records', value: fmt(totals.valid_event_district_records) },
    { label: 'P95 hazard', value: fmt(totals.p95_hazard_score, 1) },
    { label: 'Median duration', value: `${fmt(totals.median_duration_days, 1)} d` },
    { label: 'Reported fatalities', value: fmtCompact(totals.total_fatalities, 1) },
    { label: 'Reported loss, 2026 USD', value: fmtUsd(totals.total_loss_2026_usd) },
  ]);

  const yearly = appState.analytics.yearly;
  makeChart('indiaYearChart', {
    type: 'line',
    data: {
      labels: yearly.map((row) => row.year),
      datasets: [
        {
          label: 'Unique events',
          data: yearly.map((row) => row.n_events),
          borderColor: '#137a68',
          backgroundColor: 'rgba(19,122,104,0.16)',
          fill: true,
          tension: 0.22,
          pointRadius: 1.4,
        },
        {
          label: 'Event-district records',
          data: yearly.map((row) => row.n_event_district_records),
          borderColor: '#c84d3c',
          backgroundColor: '#c84d3c',
          tension: 0.22,
          pointRadius: 1.4,
        },
      ],
    },
    options: baseChartOptions(),
  });

  const causes = appState.analytics.cause_summary;
  makeChart('indiaCauseChart', {
    type: 'bar',
    data: {
      labels: causes.map((row) => row.cause),
      datasets: [{
        label: 'Records',
        data: causes.map((row) => row.n_event_district_records),
        backgroundColor: causes.map((row) => appState.analytics.cause_palette[row.cause] || '#9aa4ad'),
        borderRadius: 4,
      }],
    },
    options: baseChartOptions({
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { display: false } },
      },
    }),
  });

  renderMonthlyHeatmap();
  renderPriorityTable();
}

function heatColor(value, maxValue) {
  const t = maxValue ? Math.max(0, Math.min(1, value / maxValue)) : 0;
  const colors = ['#fff7ec', '#fee8c8', '#fdbb84', '#fc8d59', '#d7301f', '#7f0000'];
  const index = Math.min(colors.length - 1, Math.floor(t * colors.length));
  return colors[index];
}

function renderMonthlyHeatmap() {
  const data = appState.analytics.monthly;
  const wrap = byId('monthlyHeatmap');
  const maxValue = Math.max(...data.percentages.flat(), 1);
  let html = '<div class="heat-head heat-label">Cause</div>';
  data.months.forEach((month) => {
    html += `<div class="heat-head">${escapeHtml(month)}</div>`;
  });
  data.causes.forEach((cause, rowIndex) => {
    const total = data.cause_totals?.[rowIndex];
    const totalText = total === undefined ? '' : `<small>n=${fmt(total)}</small>`;
    html += `<div class="heat-label"><strong>${escapeHtml(cause)}</strong>${totalText}</div>`;
    data.percentages[rowIndex].forEach((value, colIndex) => {
      const background = heatColor(value, maxValue);
      const color = value / maxValue > 0.62 ? '#ffffff' : '#12211d';
      const count = data.counts?.[rowIndex]?.[colIndex];
      const title = count === undefined ? '' : ` title="${escapeHtml(cause)}: ${fmt(count)} records"`;
      html += `<div${title} style="background:${background};color:${color}">${value > 0 ? fmt(value, 0) : ''}</div>`;
    });
  });
  wrap.innerHTML = html;
}

function renderPriorityTable() {
  const body = byId('priorityTable');
  body.innerHTML = appState.analytics.top_districts.priority.slice(0, 12).map((row) => `
    <tr data-gid="${escapeHtml(row.gid)}">
      <td><button class="link-button" type="button" data-gid="${escapeHtml(row.gid)}">${escapeHtml(row.district)}</button></td>
      <td>${escapeHtml(row.state)}</td>
      <td class="numeric">${fmt(row.n_events)}</td>
      <td class="numeric">${fmt(row.p95_hazard_score, 1)}</td>
      <td class="numeric">${fmt(row.priority_score, 1)}</td>
    </tr>
  `).join('');
  body.querySelectorAll('button[data-gid]').forEach((button) => {
    button.addEventListener('click', () => {
      showPanel('districtPanel');
      selectDistrict(button.dataset.gid, true);
    });
  });
}

function renderStatesPanel() {
  const states = appState.analytics.state_summary.slice(0, 14);
  const causes = appState.analytics.cause_summary.slice(0, 7).map((row) => row.cause);
  const datasets = causes.map((cause) => ({
    label: cause,
    data: states.map((state) => {
      const total = Object.values(state.cause_counts || {}).reduce((sum, item) => sum + (item.records ?? item.events ?? 0), 0);
      const value = state.cause_counts?.[cause]?.records ?? state.cause_counts?.[cause]?.events ?? 0;
      return total ? (value / total) * 100 : 0;
    }),
    backgroundColor: appState.analytics.cause_palette[cause] || '#9aa4ad',
    borderColor: '#ffffff',
    borderWidth: 1,
  }));

  makeChart('stateCauseChart', {
    type: 'bar',
    data: {
      labels: states.map((state) => state.state),
      datasets,
    },
    options: baseChartOptions({
      indexAxis: 'y',
      scales: {
        x: {
          stacked: true,
          max: 100,
          ticks: { color: chartTextColor(), callback: (value) => `${value}%` },
          grid: { color: chartGridColor() },
        },
        y: { stacked: true, ticks: { color: chartTextColor() }, grid: { display: false } },
      },
    }),
  });

  const body = byId('stateTable');
  body.innerHTML = appState.analytics.state_summary.map((row) => `
    <tr>
      <td>${escapeHtml(row.state)}</td>
      <td class="numeric">${fmt(row.districts_with_records)}/${fmt(row.districts)}</td>
      <td class="numeric">${fmt(row.n_event_district_records)}</td>
      <td class="numeric">${fmt(row.p95_hazard_score, 1)}</td>
      <td>${escapeHtml(row.dominant_cause)}</td>
    </tr>
  `).join('');
}

function renderDataPanel() {
  const meta = appState.analytics.metadata;
  const totals = appState.analytics.totals;
  renderMetadata('dataMetadata', [
    { label: 'Workbook', value: meta.workbook },
    { label: 'District polygons', value: meta.district_shapefile },
    { label: 'Mapped events', value: fmt(totals.unique_events_mapped) },
    { label: 'Event-district records', value: fmt(totals.valid_event_district_records) },
    { label: 'Display units', value: meta.unit_note || 'SI-derived units and 2026 USD' },
    { label: 'Currency', value: meta.currency_note || 'Loss values shown as 2026 USD' },
    { label: 'Impact rollup', value: 'Event impacts apportioned across affected districts' },
    { label: 'Sanity flags', value: 'Flagged values excluded from rollups' },
  ]);

  byId('metricTable').innerHTML = appState.analytics.metrics.map((metric) => `
    <tr>
      <td>${escapeHtml(metric.label)}</td>
      <td>${escapeHtml(metric.unit)}</td>
      <td>${escapeHtml(metric.description)}</td>
    </tr>
  `).join('');

  byId('methodTable').innerHTML = (meta.methodology || []).map((item) => `
    <tr>
      <td>${escapeHtml(item.component)}</td>
      <td>${escapeHtml(item.method)}</td>
      <td>${escapeHtml(item.interpretation)}</td>
    </tr>
  `).join('');

  byId('paperList').innerHTML = meta.papers.map((paper) => `
    <article class="paper-item">
      <strong>${escapeHtml(paper.title)}</strong>
      <a href="${escapeHtml(paper.doi)}" target="_blank" rel="noopener">${escapeHtml(paper.doi)}</a>
      <a href="../../${escapeHtml(paper.file)}" target="_blank" rel="noopener">${escapeHtml(paper.file)}</a>
    </article>
  `).join('');
}

function showPanel(panelId) {
  document.querySelectorAll('.tabbar button').forEach((button) => {
    button.classList.toggle('active', button.dataset.panel === panelId);
  });
  document.querySelectorAll('.panel-view').forEach((panel) => {
    panel.classList.toggle('active', panel.id === panelId);
  });
  if (panelId === 'districtPanel') renderDistrictPanel();
  if (panelId === 'indiaPanel') renderIndiaPanel();
  if (panelId === 'statesPanel') renderStatesPanel();
  if (panelId === 'dataPanel') renderDataPanel();
}

function setupTabs() {
  document.querySelectorAll('.tabbar button').forEach((button) => {
    button.addEventListener('click', () => showPanel(button.dataset.panel));
  });
}

function exportFilteredCsv() {
  const columns = [
    ['gid', 'GID'],
    ['district', 'District'],
    ['state', 'State'],
    ['n_events', 'Events'],
    ['p95_hazard_score', 'P95 Hazard'],
    ['dominant_cause', 'Dominant Cause'],
    ['priority_score', 'Priority'],
    ['fatalities_apportioned_sum', 'Fatalities Apportioned'],
    ['people_affected_apportioned_sum', 'People Affected Apportioned'],
    ['crop_area_km2_apportioned_sum', 'Crop Area km2 Apportioned'],
    ['loss_2026_usd_apportioned_sum', 'Loss 2026 USD Apportioned'],
  ];
  const rows = appState.filteredFeatures.map((feature) => feature.properties);
  const csv = [
    columns.map(([, label]) => label).join(','),
    ...rows.map((row) => columns.map(([key]) => {
      const value = row[key] ?? '';
      const text = String(value).replace(/"/g, '""');
      return `"${text}"`;
    }).join(',')),
  ].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'ifi_filtered_districts.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function init() {
  const paths = window.IFI_BOOTSTRAP || { analytics: 'data/analytics.json', districts: 'data/districts.geojson' };
  const params = new URLSearchParams(window.location.search);
  const requestedMetric = params.get('metric');
  if (METRICS.some((metric) => metric.key === requestedMetric)) {
    appState.metric = requestedMetric;
  }
  const [analytics, geojson] = await Promise.all([
    fetch(paths.analytics).then((response) => response.json()),
    fetch(paths.districts).then((response) => response.json()),
  ]);

  appState.analytics = analytics;
  appState.geojson = geojson;
  appState.features = geojson.features;
  appState.featuresByGid = Object.fromEntries(appState.features.map((feature) => [feature.properties.gid, feature]));

  renderGlobalStats();
  renderMetricButtons();
  populateFilters();
  setupTabs();
  initMap();
  renderLegend();
  renderDistrictList();
  byId('exportCsvButton').addEventListener('click', exportFilteredCsv);

  const initial = analytics.top_districts.priority[0]?.gid || analytics.top_districts.events[0]?.gid;
  if (initial) selectDistrict(initial, false);
  const panelParam = params.get('panel');
  const panelId = ['district', 'india', 'states', 'data'].includes(panelParam) ? `${panelParam}Panel` : null;
  if (panelId) showPanel(panelId);
  appState.map.fitBounds(appState.districtLayer.getBounds(), { padding: [18, 18] });
  if (window.lucide) lucide.createIcons();
}

init().catch((error) => {
  console.error(error);
  setText('selectedTitle', 'Dashboard failed to load');
  setText('selectedSubtitle', error.message);
});
