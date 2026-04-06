document.addEventListener("DOMContentLoaded", () => {
  // -------------------------------------
  // CURSOR LOGIC
  // -------------------------------------
  const cursor = document.getElementById('custom-cursor');
  const cursorDot = document.getElementById('custom-cursor-dot');
  
  if (cursor && cursorDot) {
    document.addEventListener('mousemove', e => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
      cursorDot.style.left = e.clientX + 'px';
      cursorDot.style.top = e.clientY + 'px';
    });
    document.addEventListener('mousedown', () => cursor.classList.add('active'));
    document.addEventListener('mouseup', () => cursor.classList.remove('active'));
  }

  // -------------------------------------
  // PRELOADER & INITIALIZATION
  // -------------------------------------
  const initBtn = document.getElementById('initiate-btn');
  const preloader = document.getElementById('preloader');
  const introVideo = document.getElementById('intro-video');

  if (initBtn && preloader) {
    initBtn.addEventListener('click', () => {
      // Fade out enter button
      document.getElementById('enter-btn').style.opacity = '0';
      
      // Let the video glitch out smoothly after 1.5 seconds if it's there
      if (introVideo) {
        introVideo.play().catch(e => console.warn("Video blocked:", e));
      }
      
      setTimeout(() => {
        preloader.classList.add('glitch-out');
        setTimeout(() => {
          preloader.style.display = 'none';
        }, 1000);
      }, 1500);

      // Trigger initial Data Fetches
      initMap();
      fetchAI();
      fetchAnalytics();
      fetchStates();
    });
  }

  // -------------------------------------
  // SCROLLEYTELLING BLUR TRANSITIONS
  // -------------------------------------
  const sections = document.querySelectorAll('.screen-section');
  
  const observerOptions = {
    root: document.getElementById('main-scroll'),
    rootMargin: '0px',
    threshold: 0.5 // Trigger when 50% of the section is visible
  };

  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if(entry.isIntersecting) {
        entry.target.classList.add('active');
      } else {
        entry.target.classList.remove('active');
      }
    });
  }, observerOptions);

  sections.forEach(sec => sectionObserver.observe(sec));

  // -------------------------------------
  // SYSTEM CLOCK (MAP SECTION)
  // -------------------------------------
  const timeDisplay = document.getElementById('sys-time');
  if (timeDisplay) {
    setInterval(() => {
      const now = new Date();
      timeDisplay.innerText = now.toTimeString().split(' ')[0];
    }, 1000);
  }

  // -------------------------------------
  // LEAFLET MAP INITIALIZATION
  // -------------------------------------
  let map, incidentsLayer;

  function initMap() {
    if (!document.getElementById('map')) return;
    
    // Default config focuses roughly on India
    map = L.map('map', {
       zoomControl: false,
       attributionControl: false
    }).setView([22.0, 79.0], 5);

    // CartoDB Dark Matter Tile Layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19
    }).addTo(map);

    incidentsLayer = L.layerGroup().addTo(map);

    // Initial Fetch
    fetchMapData("");

    // Setup State Toggles
    document.querySelectorAll('.state-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
         const stateText = e.target.getAttribute('data-state');
         loadState(stateText);
      });
    });

    // Map Search
    const searchInput = document.getElementById('map-search');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          loadState(searchInput.value);
        }
      });
    }

    // Category Filter
    const catSelect = document.getElementById('map-category');
    if (catSelect) {
      catSelect.addEventListener('change', () => {
         loadState(searchInput ? searchInput.value : "");
      });
    }

    // Geofence Radius click
    map.on('click', async (e) => {
       const lat = e.latlng.lat;
       const lon = e.latlng.lng;
       
       document.getElementById('geofence-content').classList.add('hidden');
       const statsDiv = document.getElementById('geofence-stats');
       statsDiv.classList.remove('hidden');
       document.getElementById('geo-count').innerText = "AGGREGATING...";
       document.getElementById('geo-top-threat').innerText = "--";

       try {
         const res = await fetch(`/api/location_summary?lat=${lat}&lon=${lon}&radius_km=10`);
         if (!res.ok) throw new Error("Location API down");
         const data = await res.json();
         
         document.getElementById('geo-count').innerText = data.count || 0;
         
         if (data.distribution && Object.keys(data.distribution).length > 0) {
            const topCat = Object.keys(data.distribution).reduce((a, b) => data.distribution[a] > data.distribution[b] ? a : b);
            document.getElementById('geo-top-threat').innerText = topCat.toUpperCase();
         } else {
            document.getElementById('geo-top-threat').innerText = "CLEAR";
         }
       } catch (err) {
         document.getElementById('geo-count').innerText = "ERR";
       }
    });
  }

  function loadState(stateText) {
     incidentsLayer.clearLayers();
     fetchMapData(stateText);
  }

  async function fetchMapData(stateQuery) {
    try {
      let url = '/api/heatmap';
      let crimesUrl = '/api/crimes?limit=500';
      if (stateQuery) {
        crimesUrl += `&state=${encodeURIComponent(stateQuery)}`;
      }
      const category = document.getElementById('map-category') ? document.getElementById('map-category').value : "";
      if (category) {
        crimesUrl += `&category=${encodeURIComponent(category)}`;
      }

      // We'll plot raw crimes for exact tactical markers
      const res = await fetch(crimesUrl);
      if(!res.ok) throw new Error("Map api fail");
      const geojson = await res.json();

      let coords = [];
      if (geojson.features) {
         geojson.features.forEach(f => {
           let lat = f.geometry.coordinates[1];
           let lon = f.geometry.coordinates[0];
           coords.push([lat, lon]);
           
           // Drawing sleek neon circles
           L.circleMarker([lat, lon], {
             radius: 3,
             fillColor: '#00f6ff',
             color: '#00f6ff',
             weight: 1,
             opacity: 0.5,
             fillOpacity: 0.8
           }).addTo(incidentsLayer);
         });
      }
      
      // Auto zoom to points if any
      if (coords.length > 0) {
        const bounds = L.latLngBounds(coords);
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
      }

    } catch (err) {
      console.warn("Map data not available yet.", err);
    }
  }

  // -------------------------------------
  // AI PREDICTION HUD (SECTION 3)
  // -------------------------------------
  let aiChartInstance = null;

  async function fetchAI() {
    try {
      const res = await fetch('/api/predict');
      if(!res.ok) throw new Error("Predict backend not running");
      const data = await res.json();

      document.getElementById('ai-predict-loader').style.display = 'none';
      document.getElementById('ai-predict-data').classList.remove('hidden');

      const next = data.next_prediction;
      
      document.getElementById('pred-category').innerText = next.category;
      document.getElementById('pred-target').innerText = next.context.target || "UNKNOWN";
      
      const fakeTime = new Date(Date.now() + 1000 * 60 * 60 * 4); // +4 hours randomly
      document.getElementById('pred-time').innerText = fakeTime.toTimeString().substring(0,5);
      
      // Bar logic
      const probPercent = Math.round(next.probability * 100);
      document.getElementById('pred-prob-txt').innerText = `${probPercent}%`;
      setTimeout(() => {
        document.getElementById('pred-prob-bar').style.width = `${probPercent}%`;
      }, 500);

      // Render Chart
      renderAIChart(data.category_probs);

    } catch(err) {
      console.warn("AI Predict Error:", err);
      // Fallback UI
      document.getElementById('ai-predict-loader').innerText = "NO DATA LINK ESTABLISHED";
    }
  }

  function renderAIChart(probsMap) {
    const ctx = document.getElementById('aiChart');
    if(!ctx) return;

    if(aiChartInstance) aiChartInstance.destroy();

    const labels = Object.keys(probsMap);
    const data = labels.map(l => probsMap[l] * 100);

    // Chart JS Neon Theme Config
    Chart.defaults.color = '#718096';
    Chart.defaults.font.family = "'Orbitron', sans-serif";

    aiChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Risk Probability (%)',
          data: data,
          backgroundColor: 'rgba(0, 246, 255, 0.5)',
          borderColor: '#00f6ff',
          borderWidth: 2,
          borderRadius: 4,
          hoverBackgroundColor: 'rgba(255, 0, 193, 0.8)',
          hoverBorderColor: '#ff00c1'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, max: 100, min: 0 },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // -------------------------------------
  // ANALYTICS (SECTION 4)
  // -------------------------------------
  let trendChartInstance = null;
  
  async function fetchAnalytics() {
    try {
      const res = await fetch('/api/analysis');
      if(!res.ok) throw new Error("Analytics off");
      const data = await res.json();

      // Top sectors
      const listDiv = document.getElementById('top-sectors-list');
      listDiv.innerHTML = '';
      
      if(data.top_offenders && data.top_offenders.length > 0) {
        data.top_offenders.slice(0,5).forEach(o => {
           listDiv.innerHTML += `
             <div class="bg-gray-900 border border-gray-700 rounded p-3 flex justify-between items-center transition hover:border-cyan-400 group">
               <span class="font-orbitron text-gray-300 text-sm group-hover:text-cyan-400 transition">${o.name.toUpperCase()}</span>
               <span class="neon-magenta font-mono text-lg">${o.count}</span>
             </div>
           `;
        });
      } else {
        listDiv.innerHTML = `<div class="text-gray-500 font-mono text-center my-auto">NO CRITICAL SECTORS FOUND</div>`;
      }

      // Make 7 day array
      let ts = data.time_series || {};
      let dates = Object.keys(ts).sort();
      // Keep last 14
      dates = dates.slice(-14);
      let vals = dates.map(d => ts[d]);

      renderTrendChart(dates, vals);

    } catch (err) {
      console.warn("Analytics error", err);
      const listDiv = document.getElementById('top-sectors-list');
      listDiv.innerHTML = `<div class="text-red-500 font-mono text-center my-auto">API DISCONNECTED</div>`;
    }
  }

  function renderTrendChart(dates, vals) {
    const ctx = document.getElementById('trendChart');
    if (!ctx) return;
    
    if(trendChartInstance) trendChartInstance.destroy();

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates.map(d => d.substring(5)), // MM-DD
        datasets: [{
          label: 'Global Activity',
          data: vals,
          borderColor: '#ff00c1',
          backgroundColor: 'rgba(255, 0, 193, 0.1)',
          borderWidth: 3,
          pointBackgroundColor: '#00f6ff',
          pointBorderColor: '#000',
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // -------------------------------------
  // JURISDICTIONAL BREAKDOWN & SUBMIT INITELLIGENCE
  // -------------------------------------
  let stateChartInstance = null;
  
  async function fetchStates() {
    try {
      const res = await fetch('/api/states');
      if(!res.ok) return;
      const data = await res.json();
      const counts = data.state_counts || {};
      
      const labels = Object.keys(counts).slice(0,7); // Top 7 States
      const values = labels.map(l => counts[l]);
      
      const ctx = document.getElementById('stateChart');
      if(ctx && !stateChartInstance) {
        stateChartInstance = new Chart(ctx, {
          type: 'bar',
          data: {
             labels: labels.map(l => l.substring(0,8)),
             datasets: [{
                label: 'Incidents',
                data: values,
                backgroundColor: 'rgba(0, 246, 255, 0.4)',
                borderColor: '#00f6ff',
                borderWidth: 1
             }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { grid: { color: 'rgba(255, 255, 255, 0.05)' } },
              y: { grid: { display: false }, ticks: { font: { size: 10 } } }
            }
          }
        });
      } else if (stateChartInstance) {
        stateChartInstance.data.labels = labels.map(l => l.substring(0,8));
        stateChartInstance.data.datasets[0].data = values;
        stateChartInstance.update();
      }
    } catch(err) { console.warn(err); }
  }

  // Report crime form listener
  const reportForm = document.getElementById('report-crime-form');
  if (reportForm) {
     reportForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const city = document.getElementById('rep-city').value;
        const category = document.getElementById('rep-category').value;
        const lat = parseFloat(document.getElementById('rep-lat').value);
        const lon = parseFloat(document.getElementById('rep-lon').value);
        const statusDiv = document.getElementById('rep-status');
        
        statusDiv.classList.remove('hidden');
        statusDiv.className = 'text-center mt-2 text-fuchsia-400 font-mono text-xs animate-pulse';
        statusDiv.innerText = "TRANSMITTING DATA...";

        try {
           const res = await fetch('/api/report_crime', {
              method: 'POST',
              headers: { 
                 'Content-Type': 'application/json',
                 'Authorization': 'Bearer MOCK_TOKEN_123'
              },
              body: JSON.stringify({
                 city: city, category: category, latitude: lat, longitude: lon, state: city
              })
           });
           
           if(res.ok) {
              statusDiv.className = 'text-center mt-2 text-cyan-400 font-mono text-xs';
              statusDiv.innerText = "TRANSMIT SUCCESS. REFRESHING DB.";
              reportForm.reset();
              // Trigger refresh
              loadState("");
              fetchAI();
              fetchAnalytics();
              fetchStates();
           } else {
              throw new Error("HTTP " + res.status);
           }
        } catch(err) {
           statusDiv.className = 'text-center mt-2 text-red-500 font-mono text-xs';
           statusDiv.innerText = "FAILED TO TRANSMIT: " + err.message;
        }
     });
  }

});
