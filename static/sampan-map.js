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

  const INK = '#2A2320';
  const RED = '#9C3B24';
  const SAND = '#F4EDE1';

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
    const dirs = [['北', 'N'], ['东北', 'NE'], ['东', 'E'], ['东南', 'SE'], ['南', 'S'], ['西南', 'SW'], ['西', 'W'], ['西北', 'NW']];
    return dirs[Math.round(((ang + 360) % 360) / 45) % 8];
  }

  function dot(p, selected) {
    const certain = p.precision === 'exact' || p.precision === 'street';
    const size = selected ? 30 : 24;
    const ring = selected ? `box-shadow:0 0 0 6px rgba(156,59,36,.18),0 3px 8px rgba(0,0,0,.35);` : `box-shadow:0 3px 8px rgba(0,0,0,.32);`;
    const core = certain
      ? `background:${RED};border:3px solid ${SAND};`
      : `background:${SAND};border:3px dashed ${RED};`;
    const badge = p.linked
      ? `<span style="position:absolute;top:-12px;right:-14px;background:${INK};color:${SAND};font:700 13px/1 'Noto Serif SC',serif;padding:3px 4px 4px;border-radius:6px;">「」</span>`
      : '';
    const mark = !certain
      ? `<span style="position:absolute;top:-13px;left:-13px;background:${SAND};color:${RED};border:2px solid ${RED};width:20px;height:20px;border-radius:50%;font:700 13px/16px 'Noto Sans SC',sans-serif;text-align:center;">?</span>`
      : '';
    return `<div style="position:relative;width:${size}px;height:${size}px;border-radius:50%;${core}${ring}box-sizing:border-box;">${badge}${mark}</div>`;
  }

  function labelHtml(text) {
    return `<div style="position:absolute;left:26px;top:-4px;white-space:nowrap;background:${SAND};color:${INK};
      font:600 17px/1.2 'Noto Serif SC',serif;padding:7px 11px;border-radius:9px;border:1.5px solid rgba(42,35,32,.18);
      box-shadow:0 3px 10px rgba(0,0,0,.22);">${text}</div>`;
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
      this.style.background = '#E8E0D2';
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
        tap: true, maxZoom: 18, minZoom: 3
      });
      this._map = map;
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors', maxZoom: 19
      }).addTo(map);
      map.attributionControl.setPrefix('');
      L.control.zoom({ position: 'bottomright' }).addTo(map);
      map.on('click', () => {
        if (this._expanded) { this._expanded = null; this._draw(); }
        this.dispatchEvent(new CustomEvent('sampan-blank', { bubbles: true, composed: true }));
      });
      map.on('zoomend moveend', () => { this._draw(); this._reportOffscreen(); });
      this.resetView();
      this._draw();
      const bump = () => { map.invalidateSize(); this.resetView(); this._draw(); this._reportOffscreen(); };
      if (window.ResizeObserver) {
        let last = 0;
        this._ro = new ResizeObserver(() => {
          const h = this.clientHeight;
          if (h > 0 && h !== last) { last = h; bump(); }
        });
        this._ro.observe(this);
      }
      setTimeout(bump, 300);
      setTimeout(bump, 900);
    }

    disconnectedCallback() { if (this._ro) this._ro.disconnect(); }

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

    _clear() { this._layers.forEach((l) => this._map.removeLayer(l)); this._layers = []; }
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
      const L = this._L, map = this._map;
      this._clear();
      const pins = this._visible();

      // uncertainty halos
      pins.forEach((p) => {
        if (p.precision === 'town' || p.precision === 'region') {
          this._add(L.circle([p.lat, p.lng], {
            radius: p.precision === 'region' ? 60000 : 9000,
            color: RED, weight: 1.5, dashArray: '5 6', opacity: 0.5, fillColor: RED, fillOpacity: 0.07, interactive: false
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
          const html = `<div style="position:relative">${dot(p, sel)}${sel ? labelHtml(p.title) : ''}</div>`;
          this._marker([p.lat, p.lng], html, [sel ? 30 : 24, sel ? 30 : 24],
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
            this._add(L.polyline([center, ll], { color: INK, weight: 1.5, opacity: 0.45, dashArray: '3 5', interactive: false }));
            const html = `<div style="position:relative">${dot(p, this._selected === p.id)}${labelHtml(p.title)}</div>`;
            this._marker(ll, html, [26, 26],
              () => this.dispatchEvent(new CustomEvent('sampan-pin', { detail: { id: p.id }, bubbles: true, composed: true })), 800);
          });
          this._add(L.circleMarker(center, { radius: 5, color: INK, weight: 2, fillColor: SAND, fillOpacity: 1, interactive: false }));
        } else {
          const n = g.items.length;
          const html = `<div style="width:58px;height:58px;border-radius:50%;background:${RED};border:4px solid ${SAND};
            box-shadow:0 4px 12px rgba(0,0,0,.34);display:flex;flex-direction:column;align-items:center;justify-content:center;
            color:${SAND};font-family:'Noto Serif SC',serif;box-sizing:border-box;">
            <span style="font-size:24px;font-weight:700;line-height:1">${n}</span>
            <span style="font-size:11px;opacity:.85;line-height:1.1">个故事</span></div>`;
          this._marker(center, html, [58, 58], () => {
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
