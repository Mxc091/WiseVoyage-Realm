// DOM-only map renderer shared by H5 and App renderjs. No native map view is
// inserted into scroll-view: the map, SVG paths and labels scroll together.
import { WALK_TILES, WALK_ATTRIBUTION } from '../../shared/pedestrian-map.js'
import wanderBasemap from '../static/park-home/wander-basemap.json'

export function routeLineStyle(original, active) {
  return { color: original ? '#8b96ac' : active ? '#513dbe' : '#a69acb', weight: active ? 6 : 4,
    opacity: active ? 1 : 0.7, lineCap: 'round', lineJoin: 'round' }
}

export function loadRouteLibrary(win = window, doc = document, assetBase = './static/vendor/leaflet/') {
  if (win.__zhiyouLeafletReady) return Promise.resolve(win.L)
  if (win.__zhiyouLeafletLoading) return win.__zhiyouLeafletLoading
  const pending = new Promise((resolve, reject) => {
    if (!doc.querySelector('link[data-zhiyou-leaflet]')) {
      const css = doc.createElement('link'); css.rel = 'stylesheet'; css.href = assetBase + 'leaflet.css'
      css.dataset.zhiyouLeaflet = 'true'; doc.head.appendChild(css)
    }
    const script = doc.createElement('script'); script.src = assetBase + 'leaflet.js'
    const fail = () => { clearTimeout(timer); script.remove(); reject(new Error('地图资源加载失败，请重试')) }
    const timer = setTimeout(fail, 12000)
    script.onerror = fail
    script.onload = () => {
      if (!win.L) { fail(); return }
      clearTimeout(timer); win.__zhiyouLeafletReady = true; resolve(win.L)
    }
    doc.head.appendChild(script)
  })
  win.__zhiyouLeafletLoading = pending.catch(error => { win.__zhiyouLeafletLoading = null; throw error })
  return win.__zhiyouLeafletLoading
}

export function createRouteMap(element, report = () => {}, win = window, doc = document) {
  let map, group, contextLabels, schematic, tiles, resize, removal, payload, boundsKey = '', fitCounter = -1, version = 0, disposed = false, frame = 0
  let basemapStatus = 'loading', loadedTiles = 0, tileErrors = 0, revision = 0, drawingKey
  let mapGesture = false
  function setBasemapStatus(state) {
    basemapStatus = state
    if (!disposed) report({ state })
  }
  function showSchematic(L, compact) {
    if (schematic) return
    const pane = map.getPane('route-schematic') || map.createPane('route-schematic')
    pane.style.zIndex = '180'
    schematic = L.layerGroup().addTo(map)
    const style = { pane: 'route-schematic', interactive: false, fillOpacity: 1, weight: compact ? 0.5 : 1 }
    L.polygon(wanderBasemap.boundary, { ...style, color: '#b5d0ac', fillColor: compact ? '#dce9d4' : '#cce8c6' }).addTo(schematic)
    L.polygon(wanderBasemap.water, { ...style, color: '#a3c8d5', fillColor: compact ? '#bddae3' : '#a9d0de' }).addTo(schematic)
    L.polygon(wanderBasemap.buildings, { ...style, color: '#d9d3c8', fillColor: compact ? '#d9d3c8' : '#c0b9a9' }).addTo(schematic)
    L.polyline(wanderBasemap.paths, { ...style, color: '#fbf9ed', weight: compact ? 1 : 2 }).addTo(schematic)
    if (!compact) L.polyline(wanderBasemap.trails, { ...style, color: '#d38e7b', weight: 1.1, opacity: .8, dashArray: '3 3' }).addTo(schematic)
  }
  // Let a one-finger swipe over the Wander map scroll the surrounding page.
  const gestureStart = event => {
    if (mapGesture || (payload?.wander && event.touches.length < 2)) return
    mapGesture = true
    report({ state: 'gesture', active: true })
  }
  const gestureMove = event => { if (mapGesture && event.cancelable) event.preventDefault() }
  const gestureEnd = event => {
    if (!mapGesture || event.touches.length >= (payload?.wander ? 2 : 1)) return
    mapGesture = false
    report({ state: 'gesture', active: false })
  }
  element.addEventListener('touchstart', gestureStart, { passive: true, capture: true })
  element.addEventListener('touchmove', gestureMove, { passive: false, capture: true })
  element.addEventListener('touchend', gestureEnd, true)
  element.addEventListener('touchcancel', gestureEnd, true)
  const fitAll = () => {
    if (!map || !payload || disposed || !element.isConnected) return
    const points = payload.data.points.map(p => [p.latitude, p.longitude])
    map.stop()
    map.closePopup()
    map.invalidateSize({ pan: false })
    const padding = payload.compact ? 20 : 28
    if (points.length) map.fitBounds(win.L.latLngBounds(points), {
      padding: [padding, padding], maxZoom: points.length > 1 ? 18 : 17, animate: false,
    })
  }
  const destroy = () => {
    if (disposed) return
    element.removeEventListener('touchstart', gestureStart, true)
    element.removeEventListener('touchmove', gestureMove, true)
    element.removeEventListener('touchend', gestureEnd, true)
    element.removeEventListener('touchcancel', gestureEnd, true)
    report({ state: 'gesture', active: false })
    disposed = true; version++; win.cancelAnimationFrame(frame); resize?.disconnect(); removal?.disconnect(); map?.remove()
    map = group = contextLabels = schematic = tiles = null
  }
  // App renderjs does not provide an unmount hook. Observe actual DOM removal
  // as well as explicit H5 teardown to release tile requests and map listeners.
  if (win.MutationObserver) {
    removal = new win.MutationObserver(() => { if (!element.isConnected) destroy() })
    removal.observe(doc.body, { childList: true, subtree: true })
  }
  async function update(next) {
    payload = next; const own = ++version
    if (disposed) return
    try {
      const L = await loadRouteLibrary(win, doc, next.assetBase)
      if (disposed || own !== version || !element.isConnected) return
      if (!map) {
        const touchPage = next.wander && win.navigator?.maxTouchPoints > 0
        map = L.map(element, { zoomControl: false, attributionControl: true, scrollWheelZoom: false, zoomAnimation: false, fadeAnimation: !next.wander, dragging: !touchPage, touchZoom: true, bounceAtZoomLimits: false })
        map.attributionControl.setPrefix(false)
        if (next.wander) L.control.scale({ imperial: false, maxWidth: 70 }).addTo(map)
        // The local basemap lets the caller control which labels are visible.
        if (next.blind || (next.wander && !next.detailed)) {
          map.attributionControl.addAttribution(WALK_ATTRIBUTION)
          showSchematic(L, next.compact)
          if (next.wander) {
            contextLabels = L.layerGroup().addTo(map)
            map.on('moveend', refreshContextLabels)
          }
          basemapStatus = 'ready'
        } else {
          tiles = L.tileLayer(WALK_TILES, { maxZoom: 19, attribution: WALK_ATTRIBUTION })
          tiles.on('loading', () => { loadedTiles = tileErrors = 0; setBasemapStatus('loading') })
          tiles.on('tileload', () => { loadedTiles++ })
          tiles.on('tileerror', () => { tileErrors++ })
          tiles.on('load', () => {
            if (disposed) return
            if (tileErrors && !loadedTiles) showSchematic(L, next.compact)
            if (!tileErrors && loadedTiles && schematic) { schematic.remove(); schematic = null }
            setBasemapStatus(tileErrors ? 'tiles-error' : 'ready')
          })
          tiles.addTo(map)
        }
        group = L.layerGroup().addTo(map)
        if (win.ResizeObserver) { resize = new win.ResizeObserver(() => { win.cancelAnimationFrame(frame); frame = win.requestAnimationFrame(fitAll) }); resize.observe(element) }
      }
      if ((next.revision || 0) !== revision) {
        revision = next.revision || 0
        tiles?.redraw()
      }
      const drawing = JSON.stringify([next.data, next.original, next.activeLeg, next.currentMarker, next.markerLabels, next.steps, next.wander])
      if (drawing !== drawingKey) {
        drawRoute(L, next)
        drawingKey = drawing
      }
      const key = JSON.stringify([next.data.points, next.data.markers.map(m => m.id), next.original])
      if (key !== boundsKey || next.fitCounter !== fitCounter) { boundsKey = key; fitCounter = next.fitCounter; fitAll() }
      else if (contextLabels) refreshContextLabels()
      report({ state: basemapStatus })
    } catch (error) { if (!disposed && own === version) report({ state: 'error', message: error.message }) }
  }
  function refreshContextLabels() {
    if (!contextLabels || !Number.isFinite(map.getZoom())) return
    contextLabels.clearLayers()
    const { x: width, y: height } = map.getSize()
    const occupied = payload.data.markers.map(marker => {
      const point = map.latLngToContainerPoint([marker.latitude, marker.longitude])
      return { x: point.x + 18, y: point.y, width: 98 }
    })
    const shown = new Set(), limit = payload.compact ? 6 : 10
    for (const { position, label, kind } of wanderBasemap.labels) {
      if (shown.size >= limit) break
      if (shown.has(label)) continue
      const point = map.latLngToContainerPoint(position)
      const text = payload.mapTerms?.[label] || label
      const textWidth = text.length * 11 + 10
      if (point.x < textWidth / 2 || point.x > width - textWidth / 2 || point.y < 36 || point.y > height - 22) continue
      if (occupied.some(box => Math.abs(box.y - point.y) < 24 && Math.abs(box.x - point.x) < (box.width + textWidth) / 2)) continue
      const content = doc.createElement('span')
      content.textContent = text
      win.L.tooltip({ permanent: true, direction: 'center', opacity: 1, className: 'wander-context-label ' + kind })
        .setLatLng(position).setContent(content).addTo(contextLabels)
      occupied.push({ x: point.x, y: point.y, width: textWidth })
      shown.add(label)
    }
  }
  function drawRoute(L, next) {
    group.clearLayers()
    // Shared footpaths must not be painted over by a later muted leg.
    const lines = next.data.polyline.map((line, index) => ({ line, leg: next.data.legIndexes?.[index] ?? index }))
    lines.sort((a, b) => Number(a.leg === next.activeLeg) - Number(b.leg === next.activeLeg))
    lines.forEach(({ line, leg }) => {
      const active = next.activeLeg == null || leg === next.activeLeg
      const style=routeLineStyle(next.original,active)
      if(next.wander){ style.color=active?'#513dbe':'#9a8bc8'; style.weight=next.compact ? (active?4.5:3) : (active?7:4) }
      L.polyline(line.points.map(p => [p.latitude, p.longitude]), style)
        .on('click', () => report({ state: 'leg', index: leg })).addTo(group)
    })
    for(const points of next.steps || []) {
      L.polyline(points,{color:'#b84758',weight:3,dashArray:'5 5',interactive:false}).addTo(group)
    }
    next.data.markers.forEach(marker => {
      const gate = marker.id >= 1000, active = marker.id === next.currentMarker
      const iconSize=next.compact ? 26 : next.wander ? 40 : 36
      const icon = L.divIcon({ className: gate ? 'route-gate-marker' : 'route-order-marker',
        html: '<span class="route-map-pin' + (active ? ' current' : '') + (gate ? ' gate' : '') + '">' + (gate ? '↗' : Number(marker.id)) + '</span>',
        iconSize: [iconSize, iconSize], iconAnchor: [iconSize / 2, iconSize / 2] })
      const info = next.markerLabels?.[marker.id]
      const title = typeof info === 'string' ? info : info?.name || ''
      const interactive = !!title
      const pin = L.marker([marker.latitude, marker.longitude], { icon, title, interactive, keyboard: interactive }).addTo(group)
      if (!title) return
      const label = doc.createElement('span')
      label.textContent = title
      pin.bindTooltip(label, {
        permanent: true, direction: 'auto', offset: [iconSize / 2 + 3, 0], opacity: 1, className: 'route-stop-label',
      })
      const popup = doc.createElement('div')
      const name = doc.createElement('strong')
      name.textContent = title
      popup.appendChild(name)
      for (const text of info?.lines || []) {
        const detail = doc.createElement('div')
        detail.textContent = text
        popup.appendChild(detail)
      }
      pin.bindPopup(popup, { className: 'route-stop-popup' })
    })
  }
  return { update, destroy, fitAll }
}
