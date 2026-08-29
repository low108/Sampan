/* <sampan-map> — Leaflet + OSM map for Sampan.
   Owns tiles, certainty styling, manual clustering + spiderfy, off-screen reporting.
   API (properties/methods):
     el.setPins(pins)            pins: [{id,title,lat,lng,precision,linked,year}]
     el.setScope(idsOrNull)      restrict to a subset
     el.select(idOrNull)         highlight + centre a pin
     el.resetView()
     el.flyToPin(id)
   Events (bubbling, composed):
     sampan-pin      {id}
     sampan-cluster  {ids}
     sampan-blank    {}
     sampan-offscreen {count, ids, bearing, km}
*/
(function () {
  const CSS_URL = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  const CSS_HASH = 'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H';
  const JS_URL = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  const JS_HASH = 'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH';

  /* The map speaks the same three marks as the rest of the app, and only
     three: she named it, the system guessed it, several stories are here.
     Cream is "she named it", so clusters take the marigold to stay unambiguous
     -- the one place it is not "something of hers is new". */
  const INK = '#171009';
  const CREAM = '#FDF8EF';
  // Marigold: the cluster is the one sanctioned use away from
  // "something of hers is new", because cream is already the
  // "she named it" fill and a number needs its own colour.
  const MARIGOLD = '#F2A93C';
  const SANS = "'Archivo', system-ui, sans-serif";

  function loadLeaflet() {
    if (window.__sampanLeaflet) return window.__sampanLeaflet;
    window.__sampanLeaflet = new Promise(function (resolve, reject) {
      if (window.L) return resolve(window.L);
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = CSS_URL;
      link.integrity = CSS_HASH;
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
      const s = document.createElement('script');
      s.src = JS_URL;
      s.integrity = JS_HASH;
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(window.L); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return window.__sampanLeaflet;
  }

  function haversine(a, b) {
    const R = 6371, t = Math.PI / 180;
    const dLat = (b[0] - a[0]) * t, dLng = (b[1] - a[1]) * t;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * t) * Math.cos(b[0] * t) * Math.sin(dLng / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(x)));
  }
  function compass(from, to) {
    const dy = to[0] - from[0], dx = to[1] - from[1];
    const ang = (Math.atan2(dx, dy) * 180) / Math.PI;
    const dirs = [['north', 'N'], ['north-east', 'NE'], ['east', 'E'],
                  ['south-east', 'SE'], ['south', 'S'], ['south-west', 'SW'],
                  ['west', 'W'], ['north-west', 'NW']];
    return dirs[Math.round(((ang + 360) % 360) / 45) % 8];
  }

  const isGuess = (p) => p.precision !== 'exact' && p.precision !== 'street';

  /* Filled and solid where she said the street; hollow and dashed where the
     system guessed. A plausible wrong pin is worse than an obviously
     uncertain one, because nobody corrects what looks right. */
  function dot(p, selected) {
    const guess = isGuess(p);
    const size = guess ? 26 : 22;
    const core = guess
      ? `border:2px dashed ${CREAM};background:rgba(253,248,239,.10);`
      : `background:${CREAM};box-shadow:0 0 0 ${selected ? 7 : 4}px rgba(253,248,239,.22);`;
    const ring = guess && selected
      ? `outline:2px solid rgba(253,248,239,.5);outline-offset:5px;`
      : '';
    return `<div style="width:${size}px;height:${size}px;border-radius:50%;${core}${ring}box-sizing:border-box;"></div>`;
  }

  function dotSize(p) { return isGuess(p) ? 26 : 22; }

  function labelHtml(text) {
    return `<div style="position:absolute;left:22px;top:-6px;white-space:nowrap;background:${CREAM};color:${INK};
      font:600 14px/1.2 ${SANS};letter-spacing:-.01em;padding:8px 12px;border-radius:999px;
      box-shadow:0 4px 14px rgba(0,0,0,.34);">${text}</div>`;
  }

  class SampanMap extends HTMLElement {
    connectedCallback() {
      if (this._booted) return;
      this._booted = true;
      this.style.display = 'block';
      this.style.position = 'absolute';
      this.style.inset = '0';
      this.style.width = '100%';
      this.style.height = '100%';
      this.style.background = INK;
      const host = document.createElement('div');
      host.style.cssText = 'position:absolute;inset:0;';
      this.appendChild(host);
      this._host = host;
      this._pins = this._pins || [];
      this._scope = this._scope || null;
      this._selected = null;
      this._expanded = null;
      this._layers = [];
      loadLeaflet().then((L) => this._init(L));
    }

    _init(L) {
      this._L = L;
      const map = L.map(this._host, {
        zoomControl: false, attributionControl: true, zoomSnap: 0.25,
        /* 16, not 18: the Esri dark canvas has no tiles past 16, and a map
           that keeps zooming into blank grey is worse than one that stops. */
        tap: true, maxZoom: 16, minZoom: 3
      });
      this._map = map;
      /* A dark basemap: the pins are the only bright things on it, which is
         the whole point of the frame.

         Esri rather than CARTO, and the reason is worth recording. CARTO
         stamps "API KEY REQUIRED" diagonally across every tile served to a
         Referer it does not recognise. Localhost is exempt, so the map looked
         perfect for the entire build and only broke once it was deployed to a
         real domain — the failure mode that costs you a demo recording rather
         than a test run. Esri's dark canvas is keyless and does not check the
         referrer. Note {z}/{y}/{x}: row before column, unlike every other
         provider. */
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/' +
        'World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors',
          maxZoom: 16
        }
      ).addTo(map);
      map.attributionControl.setPrefix('');
      /* No zoom buttons: the legend already says drag to move and scroll to
         zoom, and Leaflet's white chrome is the one thing on this screen that
         would not be either a pin or her. */
      map.on('click', () => {
        if (this._expanded) { this._expanded = null; this._draw(); }
        this.dispatchEvent(new CustomEvent('sampan-blank', { bubbles: true, composed: true }));
      });
      map.on('zoomend moveend', () => { this._draw(); this._reportOffscreen(); });
      /* A Leaflet map with no centre or zoom throws on every subsequent call,
       * and resetView() sets neither when there are no pins yet. Whether that
       * happened came down to whether Leaflet was still downloading when the
       * first pins arrived: on a cold load it raced ahead, on a cached load it
       * initialised first and the map stayed viewless. Perak, wide enough to
       * hold the whole archive, until the real bounds are known. */
      map.setView([4.6, 101.1], 6);
      this.resetView();
      this._draw();
      /* Re-measure, then again on the next frame: the map screen releases the
       * phone column on wide viewports, and whether React adds that class
       * before or after Leaflet finishes downloading varies run to run. The
       * second pass costs nothing and covers the ordering where the container
       * grows in the same tick as the first measurement. */
      const bump = () => {
        map.invalidateSize({ pan: false });
        this.resetView();
        this._draw();
        this._reportOffscreen();
        requestAnimationFrame(() => {
          if (!this._map) return;
          map.invalidateSize({ pan: false });
          this._draw();
        });
      };
      window.addEventListener('resize', bump);
      this._onResize = bump;
      if (window.ResizeObserver) {
        /* Width matters as much as height. Watching only the height was
         * enough while the app was a fixed phone column; once the map screen
         * started releasing that column on wide viewports, going wide changed
         * the width alone, Leaflet never re-measured, and it went on painting
         * tiles into the old narrow box with bare page either side. */
        let lastW = 0, lastH = 0;
        this._ro = new ResizeObserver(() => {
          const w = this.clientWidth, h = this.clientHeight;
          if ((w > 0 || h > 0) && (w !== lastW || h !== lastH)) {
            lastW = w; lastH = h; bump();
          }
        });
        this._ro.observe(this);
      }
      setTimeout(bump, 300);
      setTimeout(bump, 900);
    }

    disconnectedCallback() {
      if (this._ro) this._ro.disconnect();
      if (this._onResize) window.removeEventListener('resize', this._onResize);
    }

    _visible() {
      const sc = this._scope;
      return this._pins.filter((p) => p.lat != null && (!sc || sc.indexOf(p.id) >= 0));
    }

    setPins(pins) { this._pins = pins || []; if (this._map) { this._draw(); this._reportOffscreen(); } }
    setScope(ids) {
      const changed = JSON.stringify(ids) !== JSON.stringify(this._scope);
      this._scope = ids || null;
      if (this._map && changed) { this._expanded = null; this.resetView(); this._draw(); }
    }
    select(id) {
      this._selected = id || null;
      if (!this._map) return;
      this._draw();
      const p = this._pins.find((x) => x.id === id);
      if (p && p.lat != null) this._map.panTo([p.lat, p.lng], { animate: true });
    }
    flyToPin(id) {
      const p = this._pins.find((x) => x.id === id);
      if (p && this._map) this._map.flyTo([p.lat, p.lng], p.precision === 'region' ? 8 : 15, { duration: 1.4 });
    }
    resetView() {
      if (!this._map) return;
      const v = this._visible();
      if (!v.length) return;
      const near = v.filter((p) => p.lat < 12) ;
      const use = near.length ? near : v;
      const b = this._L.latLngBounds(use.map((p) => [p.lat, p.lng]));
      this._map.fitBounds(b, { padding: [64, 96], maxZoom: 13 });
    }

    _clear() {
      /* Take the list first. _draw() is re-entrant -- fitBounds() fires
       * 'moveend' synchronously, whose handler calls _draw() again while the
       * outer one is still running -- so a list read during removal can be
       * removed twice, and Leaflet throws reading parentNode of a path it has
       * already detached. Every layer then stays recorded but absent, which is
       * how the map ended up reporting 7 layers and drawing none. */
      const layers = this._layers;
      this._layers = [];
      layers.forEach((l) => {
        try { this._map.removeLayer(l); } catch (e) { /* already detached */ }
      });
    }
    _add(l) { l.addTo(this._map); this._layers.push(l); }

    _marker(latlng, html, size, onClick, zIndex) {
      const L = this._L;
      const icon = L.divIcon({ html: html, className: '', iconSize: size, iconAnchor: [size[0] / 2, size[1] / 2] });
      const m = L.marker(latlng, { icon: icon, riseOnHover: true, zIndexOffset: zIndex || 0, keyboard: false });
      m.on('click', (e) => { L.DomEvent.stopPropagation(e); onClick(); });
      this._add(m);
      return m;
    }

    _draw() {
      if (!this._map) return;
      /* Re-entrancy guard: the nested call would otherwise clear the layers the
       * outer call is in the middle of adding. The outer call finishes the
       * drawing; the inner one would only repeat it. */
      if (this._drawing) return;
      this._drawing = true;
      try { this._drawInner(); } finally { this._drawing = false; }
    }

    _drawInner() {
      const L = this._L, map = this._map;
      this._clear();
      const pins = this._visible();

      /* The guess drawn at its own scale: a soft dashed radius, so the
         uncertainty is legible as area rather than asserted as a point. */
      pins.forEach((p) => {
        if (p.precision === 'town' || p.precision === 'region') {
          this._add(L.circle([p.lat, p.lng], {
            radius: p.precision === 'region' ? 52000 : 9000,
            color: CREAM, weight: 1, dashArray: '4 6', opacity: 0.45,
            fillColor: CREAM, fillOpacity: 0.06, interactive: false
          }));
        }
      });

      // cluster by screen distance
      const groups = [];
      pins.forEach((p) => {
        const pt = map.latLngToLayerPoint([p.lat, p.lng]);
        const g = groups.find((q) => pt.distanceTo(q.pt) < 52);
        if (g) { g.items.push(p); } else { groups.push({ pt: pt, items: [p] }); }
      });

      groups.forEach((g) => {
        if (g.items.length === 1) {
          const p = g.items[0];
          const sel = this._selected === p.id;
          const s = dotSize(p);
          const html = `<div style="position:relative">${dot(p, sel)}${sel ? labelHtml(p.title) : ''}</div>`;
          this._marker([p.lat, p.lng], html, [s, s],
            () => this.dispatchEvent(new CustomEvent('sampan-pin', { detail: { id: p.id }, bubbles: true, composed: true })),
            sel ? 900 : 0);
          return;
        }
        const ids = g.items.map((i) => i.id).sort().join('|');
        const center = map.layerPointToLatLng(g.pt);
        const open = this._expanded === ids;
        if (open) {
          g.items.forEach((p, i) => {
            const ang = (-90 + (360 / g.items.length) * i) * Math.PI / 180;
            const pt = L.point(g.pt.x + Math.cos(ang) * 84, g.pt.y + Math.sin(ang) * 84);
            const ll = map.layerPointToLatLng(pt);
            this._add(L.polyline([center, ll], { color: CREAM, weight: 1, opacity: 0.4, dashArray: '3 5', interactive: false }));
            const html = `<div style="position:relative">${dot(p, this._selected === p.id)}${labelHtml(p.title)}</div>`;
            this._marker(ll, html, [dotSize(p), dotSize(p)],
              () => this.dispatchEvent(new CustomEvent('sampan-pin', { detail: { id: p.id }, bubbles: true, composed: true })), 800);
          });
          this._add(L.circleMarker(center, { radius: 4, color: CREAM, weight: 1.5, fillColor: INK, fillOpacity: 1, interactive: false }));
        } else {
          /* Just the number. At region scale eight stories are one marigold
             disc; tapping it lists every one so none is unreachable. */
          const n = g.items.length;
          const html = `<div style="width:46px;height:46px;border-radius:50%;background:${MARIGOLD};
            box-shadow:0 6px 18px rgba(0,0,0,.38);display:flex;align-items:center;justify-content:center;
            color:${INK};font:700 18px/1 ${SANS};letter-spacing:-.02em;box-sizing:border-box;">${n}</div>`;
          this._marker(center, html, [46, 46], () => {
            this._expanded = ids; this._draw();
            this.dispatchEvent(new CustomEvent('sampan-cluster', { detail: { ids: g.items.map((i) => i.id) }, bubbles: true, composed: true }));
          }, 500);
        }
      });
    }

    _reportOffscreen() {
      const b = this._map.getBounds(), c = this._map.getCenter();
      const out = this._visible().filter((p) => !b.contains([p.lat, p.lng]));
      let detail = { count: out.length, ids: out.map((p) => p.id), bearing: null, km: 0 };
      if (out.length) {
        const far = out.reduce((a, p) => {
          const d = haversine([c.lat, c.lng], [p.lat, p.lng]);
          return d > a.d ? { d: d, p: p } : a;
        }, { d: -1, p: out[0] });
        detail.km = far.d;
        detail.bearing = compass([c.lat, c.lng], [far.p.lat, far.p.lng]);
        detail.farId = far.p.id;
      }
      this.dispatchEvent(new CustomEvent('sampan-offscreen', { detail: detail, bubbles: true, composed: true }));
    }
  }

  if (!customElements.get('sampan-map')) customElements.define('sampan-map', SampanMap);
})();
