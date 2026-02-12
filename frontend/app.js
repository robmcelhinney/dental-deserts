const DEFAULT_MAP_CENTER = [52.5, -1.5]
const DEFAULT_MAP_ZOOM = 7
const PREFERENCE_KEYS = {
    mode: "ui_pref_mode",
    metric: "ui_pref_area_metric",
    overlay: "ui_pref_area_overlay",
    coloring: "ui_pref_area_coloring",
    radius: "ui_pref_radius_km",
}

const map = L.map("map").setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM)
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 18,
    attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
}).addTo(map)

const postcodeInput = document.getElementById("postcode")
const searchButton = document.getElementById("search")
const radiusSelect = document.getElementById("radius")
const modeSelect = document.getElementById("mode")
const searchModeRadiusButton = document.getElementById("search-mode-radius")
const searchModeViewportButton = document.getElementById("search-mode-viewport")
const resetViewButton = document.getElementById("reset-view")
const postcodeControlsEl = document.getElementById("postcode-controls")
const radiusControlsEl = document.getElementById("radius-controls")
const viewportHintEl = document.getElementById("viewport-hint")
const radiusValueEl = document.getElementById("radius-value")
const areaOverlayCheckbox = document.getElementById("area-overlay")
const areaMetricSelect = document.getElementById("area-metric")
const areaColoringSelect = document.getElementById("area-coloring")
const areaColoringControlsEl = document.getElementById("area-coloring-controls")
const coverageBannerEl = document.getElementById("coverage-banner")
const statusEl = document.getElementById("status")
const desertBannerEl = document.getElementById("desert-banner")
const compareCardEl = document.getElementById("compare-card")
const dataSnapshotEl = document.getElementById("data-snapshot")
const resultsTitleEl = document.getElementById("results-title")
const resultsEl = document.getElementById("results")
const resultsEmptyEl = document.getElementById("results-empty")
const loadMoreButton = document.getElementById("load-more")

const areaMetricConfig = {
    pressure: {
        key: "practices_per_10k",
        label: "Practices per 10k",
        format: (v) => v.toFixed(2),
    },
    adults_density: {
        key: "accepting_adults_per_10k_adults",
        label: "MSOA NHS adult-accepting per 10k adults",
        format: (v) => v.toFixed(2),
    },
    deprivation: {
        key: "imd_decile",
        label: "IMD decile",
        format: (v) => String(v),
    },
    desert_risk: {
        key: "desert_risk_score",
        label: "Dental desert risk score",
        format: (v) => v.toFixed(2),
    },
}
const UK_POSTCODE_RE = /^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$/

let practices = []
let markers = []
let markersLayer = null
let userMarker = null
let rankedResults = []
let visibleResultCount = 25
let markerByPracticeId = new Map()
let activePracticeId = null
let lastSearchPoint = null
let lastSearchContext = ""
let forcedCompareAreaCode = null
let forcedOutlineLsoaCode = null
let searchMode = "radius"
let radiusCircle = null
const MAX_MAP_MARKERS = 1000
const VIEWPORT_MIN_ZOOM = 9
const MAX_OVERLAY_AREAS = 500
const OVERLAY_VIEW_PADDING = 0.25
const OUTSIDE_ENGLAND_HOVER_WARNING =
    "Area info is currently England-only. Hovered area is outside England."
const AREA_COLOR_SCHEMES = {
    contrast: [
        "#f7fbff",
        "#deebf7",
        "#9ecae1",
        "#6baed6",
        "#3182bd",
        "#08519c",
    ],
    off: ["#dfe3e8"],
}

let areasGeojson = null
let areaMetrics = {}
let areaLayer = null
let selectedAreaOutlineLayer = null
let areaScale = { min: 0, max: 1 }
let areaBreaks = [0, 1]
let areaDataLoaded = false
let areaDataLoadPromise = null
let areaFeatureIndex = []
let areaColorScheme = "contrast"
let dataSnapshotLabel = "unknown"

const ENGLAND_WALES_BOUNDS = {
    minLat: 49.8,
    maxLat: 55.9,
    minLon: -6.6,
    maxLon: 2.1,
}

const areaInfoControl = L.control({ position: "topright" })
areaInfoControl.onAdd = function onAdd() {
    this._div = L.DomUtil.create("div", "area-info-control")
    this.update()
    return this._div
}
areaInfoControl.update = function update(areaCode = null) {
    if (!this._div) {
        return
    }
    if (!areaCode || !areaMetrics[areaCode]) {
        this._div.innerHTML =
            `<div class="area-info-title">Area info</div>` +
            `<div class="area-info-empty">Hover an area</div>`
        return
    }

    const metric = areaMetricConfig[areaMetricSelect.value]
    const data = areaMetrics[areaCode]
    const value = Number(data[metric.key])
    const valueText = Number.isFinite(value) ? metric.format(value) : "unknown"

    this._div.innerHTML =
        `<div class="area-info-title">${data.area_name}</div>` +
        `<div class="area-info-row"><span>${metric.label}</span><strong>${valueText}</strong></div>` +
        `<div class="area-info-row"><span>Practices per 10k</span><strong>${Number(data.practices_per_10k).toFixed(2)}</strong></div>` +
        `<div class="area-info-row"><span>IMD decile</span><strong>${data.imd_decile}</strong></div>`
}

const legendControl = L.control({ position: "bottomright" })
legendControl.onAdd = function onAdd() {
    this._div = L.DomUtil.create("div", "area-legend")
    this.update()
    return this._div
}
legendControl.update = function update() {
    if (!this._div) {
        return
    }
    const metric = areaMetricConfig[areaMetricSelect.value]
    if (areaColorScheme === "off") {
        this._div.innerHTML =
            `<strong>${metric.label}</strong>` +
            `<div class="legend-range">Colouring is off</div>` +
            `<div><span style="background:#dfe3e8"></span>Neutral area style</div>`
        return
    }
    const breaks = areaBreaks
    const colors = getAreaColors()
    const rows = []
    for (let i = 0; i < colors.length; i += 1) {
        const from = breaks[i]
        const to = breaks[i + 1] !== undefined ? breaks[i + 1] : from
        rows.push(
            `<div><span style="background:${colors[i]}"></span>${metric.format(from)} - ${metric.format(to)}</div>`,
        )
    }

    this._div.innerHTML =
        `<strong>${metric.label}</strong>` +
        `<div class="legend-range">Range: ${metric.format(areaScale.min)} - ${metric.format(areaScale.max)}</div>` +
        rows.join("")
}

function normalizePostcode(value) {
    return value.trim().toUpperCase()
}

function normalizeQuery(value) {
    return value.trim()
}

function isLikelyUkPostcode(value) {
    const normalized = normalizePostcode(value).replace(/\s+/g, "")
    return UK_POSTCODE_RE.test(normalized)
}

function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371
    const dLat = ((lat2 - lat1) * Math.PI) / 180
    const dLon = ((lon2 - lon1) * Math.PI) / 180
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((lat1 * Math.PI) / 180) *
            Math.cos((lat2 * Math.PI) / 180) *
            Math.sin(dLon / 2) ** 2
    return 2 * R * Math.asin(Math.sqrt(a))
}

function markerColor(props) {
    if (
        props.accepting_adults === "yes" ||
        props.accepting_children === "yes"
    ) {
        return "#0b6e4f"
    }
    if (props.accepting_adults === "no" && props.accepting_children === "no") {
        return "#a43d2f"
    }
    return "#7c8794"
}

function availabilityLabel(value) {
    if (value === "yes") {
        return "Accepting"
    }
    if (value === "no") {
        return "Not accepting"
    }
    return "Unknown"
}

function availabilityClass(value) {
    if (value === "yes") {
        return "yes"
    }
    if (value === "no") {
        return "no"
    }
    return "unknown"
}

function resultStatusType(item) {
    if (item.accepting_adults === "yes" || item.accepting_children === "yes") {
        return "yes"
    }
    if (item.accepting_adults === "no" && item.accepting_children === "no") {
        return "no"
    }
    return "unknown"
}

function markerLimitForCurrentMode() {
    if (searchMode !== "viewport") {
        return MAX_MAP_MARKERS
    }
    const zoom = map.getZoom()
    if (zoom < 12) {
        return 200
    }
    if (zoom < 13) {
        return 400
    }
    return 800
}

function updateResultsTitle() {
    if (!resultsTitleEl) {
        return
    }
    resultsTitleEl.textContent =
        searchMode === "viewport"
            ? "Nearest to map center"
            : "Nearest Practices"
}

function saveUiPreferences() {
    localStorage.setItem(PREFERENCE_KEYS.mode, searchMode)
    localStorage.setItem(PREFERENCE_KEYS.metric, areaMetricSelect.value)
    localStorage.setItem(
        PREFERENCE_KEYS.overlay,
        areaOverlayCheckbox.checked ? "1" : "0",
    )
    localStorage.setItem(PREFERENCE_KEYS.coloring, areaColorScheme)
    localStorage.setItem(PREFERENCE_KEYS.radius, String(radiusSelect.value))
}

function restoreUiPreferences() {
    const savedRadius = localStorage.getItem(PREFERENCE_KEYS.radius)
    if (savedRadius) {
        const parsed = Number(savedRadius)
        if (Number.isFinite(parsed) && parsed >= 0.5 && parsed <= 50) {
            radiusSelect.value = String(parsed)
        }
    }

    const savedMetric = localStorage.getItem(PREFERENCE_KEYS.metric)
    if (savedMetric && areaMetricConfig[savedMetric]) {
        areaMetricSelect.value = savedMetric
    }

    const savedColoring = localStorage.getItem(PREFERENCE_KEYS.coloring)
    if (savedColoring && AREA_COLOR_SCHEMES[savedColoring]) {
        areaColorScheme = savedColoring
        if (areaColoringSelect) {
            areaColoringSelect.value = savedColoring
        }
    }

    const savedOverlay = localStorage.getItem(PREFERENCE_KEYS.overlay)
    if (savedOverlay === "1" || savedOverlay === "0") {
        areaOverlayCheckbox.checked = savedOverlay === "1"
    }

    const savedMode = localStorage.getItem(PREFERENCE_KEYS.mode)
    if (savedMode === "viewport" || savedMode === "radius") {
        searchMode = savedMode
    }
}

function formatSnapshotDate(isoText) {
    if (typeof isoText !== "string" || !isoText) {
        return "unknown"
    }
    const dt = new Date(isoText)
    if (Number.isNaN(dt.getTime())) {
        return "unknown"
    }
    return dt.toISOString().slice(0, 10)
}

function updateSnapshotText() {
    if (!dataSnapshotEl) {
        return
    }
    dataSnapshotEl.textContent = `Data snapshot: ${dataSnapshotLabel}`
}

function compareCardFooterHtml() {
    return `<div class="compare-footer">Data snapshot: ${dataSnapshotLabel}</div>`
}

async function loadSnapshotDate() {
    try {
        const resp = await fetch("data/processed/qa_report.json")
        if (!resp.ok) {
            return
        }
        const payload = await resp.json()
        dataSnapshotLabel = formatSnapshotDate(payload.generated_at_utc)
    } catch (_err) {
        dataSnapshotLabel = "unknown"
    } finally {
        updateSnapshotText()
    }
}

function clearPracticeMarkers() {
    if (markersLayer) {
        markersLayer.clearLayers()
        map.removeLayer(markersLayer)
        markersLayer = null
    } else {
        for (const marker of markers) {
            map.removeLayer(marker)
        }
    }
    markers = []
    markerByPracticeId = new Map()
}

function updateActiveResult() {
    const rows = resultsEl.querySelectorAll("li")
    for (const row of rows) {
        row.classList.toggle(
            "active",
            row.dataset.practiceId === activePracticeId,
        )
    }
}

function setActivePractice(practiceId) {
    activePracticeId = practiceId
    updateActiveResult()
}

function buildRankedResults(lat, lon) {
    const radiusKm = Number(radiusSelect.value)
    const mode = modeSelect.value

    return practices
        .map((p) => ({
            ...p,
            distance_km: haversineKm(lat, lon, p.lat, p.lon),
        }))
        .filter((p) => p.distance_km <= radiusKm)
        .filter((p) => {
            if (mode === "adult") {
                return p.accepting_adults === "yes"
            }
            if (mode === "children") {
                return p.accepting_children === "yes"
            }
            return true
        })
        .sort((a, b) => a.distance_km - b.distance_km)
}

function buildViewportResults() {
    const mode = modeSelect.value
    const bounds = map.getBounds()
    const center = map.getCenter()
    return practices
        .filter((p) => bounds.contains([p.lat, p.lon]))
        .map((p) => ({
            ...p,
            distance_km: haversineKm(center.lat, center.lng, p.lat, p.lon),
        }))
        .filter((p) => {
            if (mode === "adult") {
                return p.accepting_adults === "yes"
            }
            if (mode === "children") {
                return p.accepting_children === "yes"
            }
            return true
        })
        .sort((a, b) => a.distance_km - b.distance_km)
}

function renderResults() {
    resultsEl.innerHTML = ""
    rankedResults.slice(0, visibleResultCount).forEach((item) => {
        const li = document.createElement("li")
        const statusType = resultStatusType(item)
        li.dataset.practiceId = item.practice_id
        li.tabIndex = 0

        const row = document.createElement("div")
        row.className = "result-row"
        const dot = document.createElement("span")
        dot.className = `result-dot ${statusType}`
        const title = document.createElement("span")
        title.className = "result-name"
        title.textContent = item.practice_name
        const distance = document.createElement("span")
        distance.className = "result-distance"
        distance.textContent = `${item.distance_km.toFixed(2)} km`
        row.appendChild(dot)
        row.appendChild(title)
        row.appendChild(distance)

        const meta = document.createElement("div")
        meta.className = "result-meta"
        meta.textContent = `Adults: ${availabilityLabel(item.accepting_adults)} | Children: ${availabilityLabel(item.accepting_children)}`

        li.appendChild(row)
        li.appendChild(meta)
        li.addEventListener("click", () => {
            setActivePractice(item.practice_id)
            const marker = markerByPracticeId.get(item.practice_id)
            if (marker) {
                marker.openPopup()
                map.panTo(marker.getLatLng())
            }
        })
        li.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault()
                li.click()
            }
        })
        resultsEl.appendChild(li)
    })
    resultsEmptyEl.classList.toggle("is-empty", rankedResults.length > 0)
    resultsEl.classList.toggle("is-empty", rankedResults.length === 0)
    loadMoreButton.style.display =
        rankedResults.length > 0 && visibleResultCount < rankedResults.length
            ? "block"
            : "none"
    updateActiveResult()
}

function renderMarkers(sorted) {
    clearPracticeMarkers()
    markersLayer = L.layerGroup()
    const markerLimit = markerLimitForCurrentMode()
    sorted.slice(0, markerLimit).forEach((item) => {
        const marker = L.circleMarker([item.lat, item.lon], {
            radius: 6.5,
            color: "#ffffff",
            weight: 1.3,
            fillColor: markerColor(item),
            fillOpacity: 0.9,
        })
        const adultStatus = item.accepting_adults || "unknown"
        const childrenStatus = item.accepting_children || "unknown"
        const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(item.address + " " + item.postcode)}`
        marker.bindPopup(
            `<div class="clinic-popup">` +
                `<div class="clinic-popup__title">${item.practice_name}</div>` +
                `<div class="clinic-popup__address">${item.address}</div>` +
                `<div class="clinic-popup__postcode">${item.postcode}</div>` +
                `<div class="clinic-popup__status-row">` +
                `<span class="clinic-popup__status-label">NHS adults</span>` +
                `<span class="clinic-popup__pill ${availabilityClass(adultStatus)}">${availabilityLabel(adultStatus)}</span>` +
                `</div>` +
                `<div class="clinic-popup__status-row">` +
                `<span class="clinic-popup__status-label">NHS children</span>` +
                `<span class="clinic-popup__pill ${availabilityClass(childrenStatus)}">${availabilityLabel(childrenStatus)}</span>` +
                `</div>` +
                `<a class="clinic-popup__link" target="_blank" rel="noopener noreferrer" href="${mapsUrl}">Open in Google Maps</a>` +
                `</div>`,
            { className: "clinic-popup-shell", maxWidth: 340 },
        )
        marker.on("click", () => {
            setActivePractice(item.practice_id)
        })
        markersLayer.addLayer(marker)
        markers.push(marker)
        markerByPracticeId.set(item.practice_id, marker)
    })
    map.addLayer(markersLayer)
}

function updateDentalDesertBanner() {
    if (searchMode === "viewport") {
        desertBannerEl.textContent = ""
        desertBannerEl.classList.add("is-empty")
        return
    }
    const radiusKm = Number(radiusSelect.value)
    const radiusLabel = `${radiusKm.toFixed(1)} km`
    const mode = modeSelect.value
    if (mode === "adult" && rankedResults.length === 0) {
        desertBannerEl.textContent = `No practices reporting NHS adult availability within ${radiusLabel}.`
        desertBannerEl.classList.remove("is-empty")
        return
    }
    if (mode === "children" && rankedResults.length === 0) {
        desertBannerEl.textContent = `No practices reporting NHS children availability within ${radiusLabel}.`
        desertBannerEl.classList.remove("is-empty")
        return
    }
    desertBannerEl.textContent = ""
    desertBannerEl.classList.add("is-empty")
}

function updateRadiusDisplay() {
    if (radiusValueEl) {
        radiusValueEl.textContent = `${Number(radiusSelect.value).toFixed(1)} km`
    }
}

function updateRadiusCircle() {
    if (!lastSearchPoint || searchMode !== "radius") {
        if (radiusCircle) {
            map.removeLayer(radiusCircle)
            radiusCircle = null
        }
        return
    }
    const radiusMeters = Number(radiusSelect.value) * 1000
    if (!radiusCircle) {
        radiusCircle = L.circle([lastSearchPoint.lat, lastSearchPoint.lon], {
            radius: radiusMeters,
            color: "#5d6b7a",
            weight: 1,
            fillColor: "#8da0b6",
            fillOpacity: 0.08,
            interactive: false,
        }).addTo(map)
        return
    }
    radiusCircle.setLatLng([lastSearchPoint.lat, lastSearchPoint.lon])
    radiusCircle.setRadius(radiusMeters)
}

function colorForValue(value) {
    if (areaColorScheme === "off") {
        return "#dfe3e8"
    }
    const colors = getAreaColors()
    if (!Number.isFinite(value)) {
        return "#d9dee3"
    }
    if (!areaBreaks.length) {
        return colors[0]
    }
    for (let i = 0; i < colors.length; i += 1) {
        const upper = areaBreaks[i + 1]
        if (upper === undefined || value <= upper) {
            return colors[i]
        }
    }
    return colors[colors.length - 1]
}

function getAreaColors() {
    return AREA_COLOR_SCHEMES[areaColorScheme] || AREA_COLOR_SCHEMES.contrast
}

function getAreaMetricValue(areaCode) {
    const metric = areaMetricConfig[areaMetricSelect.value]
    const data = areaMetrics[areaCode]
    if (!data) {
        return null
    }
    const value = Number(data[metric.key])
    return Number.isFinite(value) ? value : null
}

function pointInRing(lat, lon, ring) {
    let inside = false
    let j = ring.length - 1
    for (let i = 0; i < ring.length; i += 1) {
        const xi = ring[i][0]
        const yi = ring[i][1]
        const xj = ring[j][0]
        const yj = ring[j][1]
        const intersects =
            yi > lat !== yj > lat &&
            lon < ((xj - xi) * (lat - yi)) / (yj - yi || 1e-12) + xi
        if (intersects) {
            inside = !inside
        }
        j = i
    }
    return inside
}

function pointInPolygon(lat, lon, polygonCoords) {
    if (!polygonCoords || !polygonCoords.length) {
        return false
    }
    const outer = polygonCoords[0] || []
    if (!pointInRing(lat, lon, outer)) {
        return false
    }
    for (let i = 1; i < polygonCoords.length; i += 1) {
        if (pointInRing(lat, lon, polygonCoords[i] || [])) {
            return false
        }
    }
    return true
}

function featureContainsPoint(feature, lat, lon) {
    const geom = feature && feature.geometry
    if (!geom) {
        return false
    }
    if (geom.type === "Polygon") {
        return pointInPolygon(lat, lon, geom.coordinates)
    }
    if (geom.type === "MultiPolygon") {
        for (const polygon of geom.coordinates || []) {
            if (pointInPolygon(lat, lon, polygon)) {
                return true
            }
        }
    }
    return false
}

function centroidOfRing(ring) {
    if (!ring.length) {
        return { lat: 0, lon: 0 }
    }
    let latSum = 0
    let lonSum = 0
    for (const coord of ring) {
        lonSum += coord[0]
        latSum += coord[1]
    }
    return { lat: latSum / ring.length, lon: lonSum / ring.length }
}

function centroidOfFeature(feature) {
    const geom = feature && feature.geometry
    if (!geom) {
        return null
    }
    if (geom.type === "Polygon") {
        return centroidOfRing((geom.coordinates && geom.coordinates[0]) || [])
    }
    if (geom.type === "MultiPolygon") {
        const polygons = geom.coordinates || []
        let best = null
        let bestLen = -1
        for (const polygon of polygons) {
            const ring = (polygon && polygon[0]) || []
            if (ring.length > bestLen) {
                bestLen = ring.length
                best = ring
            }
        }
        return centroidOfRing(best || [])
    }
    return null
}

function featureBoundsFromGeometry(geom) {
    if (!geom || !geom.coordinates) {
        return null
    }
    let minLon = Number.POSITIVE_INFINITY
    let minLat = Number.POSITIVE_INFINITY
    let maxLon = Number.NEGATIVE_INFINITY
    let maxLat = Number.NEGATIVE_INFINITY

    function visitCoord(coord) {
        if (!Array.isArray(coord) || coord.length < 2) {
            return
        }
        const lon = Number(coord[0])
        const lat = Number(coord[1])
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
            return
        }
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
    }

    function walk(node) {
        if (!Array.isArray(node) || !node.length) {
            return
        }
        if (typeof node[0] === "number") {
            visitCoord(node)
            return
        }
        for (const child of node) {
            walk(child)
        }
    }

    walk(geom.coordinates)
    if (
        !Number.isFinite(minLon) ||
        !Number.isFinite(minLat) ||
        !Number.isFinite(maxLon) ||
        !Number.isFinite(maxLat)
    ) {
        return null
    }
    return { minLon, minLat, maxLon, maxLat }
}

function boundsIntersect(a, b) {
    if (!a || !b) {
        return false
    }
    return !(
        a.maxLon < b.minLon ||
        a.minLon > b.maxLon ||
        a.maxLat < b.minLat ||
        a.minLat > b.maxLat
    )
}

function mapBoundsToBox(bounds) {
    const sw = bounds.getSouthWest()
    const ne = bounds.getNorthEast()
    return {
        minLon: sw.lng,
        minLat: sw.lat,
        maxLon: ne.lng,
        maxLat: ne.lat,
    }
}

function selectVisibleAreaFeatures() {
    if (!areaFeatureIndex.length) {
        return []
    }
    const paddedBounds = map.getBounds().pad(OVERLAY_VIEW_PADDING)
    const visibleBox = mapBoundsToBox(paddedBounds)
    const candidates = areaFeatureIndex.filter(
        (entry) =>
            boundsIntersect(entry.bounds, visibleBox) &&
            isEnglandAreaCode(
                entry.feature &&
                    entry.feature.properties &&
                    entry.feature.properties.area_code,
            ),
    )
    if (candidates.length <= MAX_OVERLAY_AREAS) {
        return candidates.map((entry) => entry.feature)
    }

    const center = map.getCenter()
    candidates.sort((a, b) => {
        const da = haversineKm(
            center.lat,
            center.lng,
            a.centroid.lat,
            a.centroid.lon,
        )
        const db = haversineKm(
            center.lat,
            center.lng,
            b.centroid.lat,
            b.centroid.lon,
        )
        return da - db
    })
    return candidates.slice(0, MAX_OVERLAY_AREAS).map((entry) => entry.feature)
}

function findAreaCodeByPoint(lat, lon) {
    if (!areasGeojson || !areasGeojson.features) {
        return null
    }
    for (const feature of areasGeojson.features) {
        const areaCode = feature.properties.area_code
        if (!areaCode) {
            continue
        }
        if (featureContainsPoint(feature, lat, lon)) {
            return areaCode
        }
    }

    let nearestCode = null
    let nearestDistance = Number.POSITIVE_INFINITY
    for (const feature of areasGeojson.features) {
        const areaCode = feature.properties.area_code
        if (!areaCode) {
            continue
        }
        const centroid = centroidOfFeature(feature)
        if (!centroid) {
            continue
        }
        const distance = haversineKm(lat, lon, centroid.lat, centroid.lon)
        if (distance < nearestDistance) {
            nearestDistance = distance
            nearestCode = areaCode
        }
    }
    return nearestCode
}

function findContainingAreaCodeByPoint(lat, lon) {
    if (!areasGeojson || !areasGeojson.features) {
        return null
    }
    for (const feature of areasGeojson.features) {
        const areaCode = feature.properties.area_code
        if (!areaCode) {
            continue
        }
        if (featureContainsPoint(feature, lat, lon)) {
            return areaCode
        }
    }
    return null
}

function findContainingEnglandAreaCodeByPoint(lat, lon) {
    const areaCode = findContainingAreaCodeByPoint(lat, lon)
    return isEnglandAreaCode(areaCode) ? areaCode : null
}

function percentileRank(value, values) {
    if (!values.length) {
        return null
    }
    let below = 0
    let equal = 0
    for (const v of values) {
        if (v < value) {
            below += 1
        } else if (v === value) {
            equal += 1
        }
    }
    // Midrank percentile handles ties without forcing all equal values to 100th.
    return ((below + 0.5 * equal) / values.length) * 100
}

function formatOrdinal(value) {
    const n = Math.round(value)
    const mod100 = n % 100
    if (mod100 >= 11 && mod100 <= 13) {
        return `${n}th`
    }
    const mod10 = n % 10
    if (mod10 === 1) {
        return `${n}st`
    }
    if (mod10 === 2) {
        return `${n}nd`
    }
    if (mod10 === 3) {
        return `${n}rd`
    }
    return `${n}th`
}

function compareDirection(metricKey) {
    if (metricKey === "desert_risk_score") {
        return "lower_better"
    }
    return "higher_better"
}

function metricDefinition(metricKey) {
    if (metricKey === "practices_per_10k") {
        return "Estimated number of dental practices per 10,000 residents in this MSOA."
    }
    if (metricKey === "accepting_adults_per_10k_adults") {
        return "Estimated number of practices reporting NHS adult acceptance per 10,000 adults in this MSOA."
    }
    if (metricKey === "imd_decile") {
        return "IMD decile from 1 to 10. Lower values indicate higher deprivation."
    }
    if (metricKey === "desert_risk_score") {
        return "Composite score combining low practice density, low adult-accepting density, and deprivation."
    }
    return "Area-level metric for this MSOA."
}

function buildCompareHelpHtml(
    metricLabel,
    metricKey,
    directionText,
    sampleSize,
) {
    return (
        `<details class="compare-help">` +
        `<summary>How to read this</summary>` +
        `<div class="compare-help-body">` +
        `<div><strong>${metricLabel}</strong>: ${metricDefinition(metricKey)}</div>` +
        `<div><strong>Percentile</strong>: rank of this area against currently loaded England MSOAs (${sampleSize} areas).</div>` +
        `<div><strong>England range</strong>: lowest to highest loaded values for this metric.</div>` +
        `<div><strong>Direction</strong>: ${directionText}.</div>` +
        `</div>` +
        `</details>`
    )
}

function compareBadge(metricKey, percentile) {
    const direction = compareDirection(metricKey)
    if (direction === "lower_better") {
        if (percentile <= 25) {
            return { label: "Lower risk", cls: "good" }
        }
        if (percentile <= 75) {
            return { label: "Moderate risk", cls: "mid" }
        }
        return { label: "Higher risk", cls: "bad" }
    }

    if (percentile >= 75) {
        return { label: "Stronger access", cls: "good" }
    }
    if (percentile >= 25) {
        return { label: "Typical range", cls: "mid" }
    }
    return { label: "Weaker access", cls: "bad" }
}

function hasValidDenominator(area, metricKey) {
    if (metricKey === "practices_per_10k") {
        return Number(area.population_total) > 0
    }
    if (metricKey === "accepting_adults_per_10k_adults") {
        return Number(area.population_adults) > 0
    }
    if (metricKey === "accepting_children_per_10k_children") {
        return Number(area.population_children) > 0
    }
    return true
}

function countNearbyAcceptingAdults() {
    if (!lastSearchPoint) {
        return null
    }
    const radiusKm = Number(radiusSelect.value)
    const count = practices.filter((p) => {
        if (p.accepting_adults !== "yes") {
            return false
        }
        const d = haversineKm(
            lastSearchPoint.lat,
            lastSearchPoint.lon,
            p.lat,
            p.lon,
        )
        return d <= radiusKm
    }).length
    return { count, radiusKm }
}

function updateCompareCard(searchLat, searchLon) {
    if (!compareCardEl) {
        return
    }
    if (
        !areasGeojson ||
        !Object.keys(areaMetrics).length ||
        searchLat == null ||
        searchLon == null
    ) {
        compareCardEl.textContent = ""
        compareCardEl.classList.add("is-empty")
        clearSelectedAreaOutline()
        return
    }
    const hasAreaFeatures = Boolean(
        areasGeojson && areasGeojson.features && areasGeojson.features.length,
    )
    const inLoadedCoverage =
        hasAreaFeatures &&
        Boolean(findContainingEnglandAreaCodeByPoint(searchLat, searchLon))
    const compareFooter = compareCardFooterHtml()
    if (!inLoadedCoverage) {
        compareCardEl.innerHTML =
            `<div class="compare-title">MSOA-level benchmark</div>` +
            `<div class="compare-subtitle">Area benchmark is currently available for England only.</div>` +
            compareFooter
        compareCardEl.classList.remove("is-empty")
        clearSelectedAreaOutline()
        return
    }

    let areaCode = null
    if (searchMode === "radius") {
        areaCode =
            forcedCompareAreaCode || findAreaCodeByPoint(searchLat, searchLon)
    } else {
        areaCode =
            forcedCompareAreaCode || findAreaCodeByPoint(searchLat, searchLon)
    }
    if (!areaCode || !areaMetrics[areaCode]) {
        if (searchMode === "radius") {
            compareCardEl.innerHTML =
                `<div class="compare-title">MSOA-level benchmark</div>` +
                `<div class="compare-subtitle">No benchmark area is loaded for this postcode yet. Try another postcode or rebuild data coverage.</div>` +
                compareFooter
        } else {
            compareCardEl.innerHTML =
                `<div class="compare-title">MSOA-level benchmark</div>` +
                `<div class="compare-subtitle">Compare card unavailable for this location.</div>` +
                compareFooter
        }
        compareCardEl.classList.remove("is-empty")
        clearSelectedAreaOutline()
        return
    }
    renderSelectedAreaOutline(areaCode, searchLat, searchLon)

    const metric = areaMetricConfig[areaMetricSelect.value]
    const localArea = areaMetrics[areaCode]
    const localValue = Number(localArea[metric.key])
    const compareHeader =
        `<div class="compare-title">MSOA-level benchmark</div>` +
        `<div class="compare-subtitle">Area-based context for this map point (not your radius search). Blue outline shows the local boundary used for this point.</div>`
    if (!Number.isFinite(localValue)) {
        if (metric.key === "imd_decile") {
            compareCardEl.innerHTML =
                compareHeader +
                `<div class="compare-area">${localArea.area_name}</div>` +
                `<div class="compare-note">IMD decile is not available for this area yet. This usually means the location is outside current England/Wales IMD coverage or area-code mapping is incomplete.</div>` +
                compareFooter
        } else {
            compareCardEl.innerHTML =
                compareHeader +
                `<div class="compare-area">${localArea.area_name}</div>` +
                `<div class="compare-note">Compare card unavailable for this metric.</div>` +
                compareFooter
        }
        compareCardEl.classList.remove("is-empty")
        return
    }

    const comparableAreas = Object.keys(areaMetrics)
        .map((code) => areaMetrics[code])
        .filter((area) => hasValidDenominator(area, metric.key))
    const allValues = comparableAreas
        .map((area) => Number(area[metric.key]))
        .filter((v) => Number.isFinite(v))

    if (!hasValidDenominator(localArea, metric.key) || allValues.length < 30) {
        const practiceCounts = Object.keys(areaMetrics)
            .map((code) => Number(areaMetrics[code].practice_count))
            .filter((v) => Number.isFinite(v))
        const localPracticeCount = Number(localArea.practice_count) || 0
        const practicePercentile = percentileRank(
            localPracticeCount,
            practiceCounts,
        )

        const fallbackDirectionText =
            compareDirection(metric.key) === "lower_better"
                ? "Lower is better"
                : "Higher is better"
        const compareHelp = buildCompareHelpHtml(
            metric.label,
            metric.key,
            fallbackDirectionText,
            allValues.length,
        )
        compareCardEl.innerHTML =
            compareHeader +
            `<div class="compare-area">${localArea.area_name}</div>` +
            `<div class="compare-note">Per-capita comparison is limited until full denominator coverage is loaded.</div>` +
            `<div class="compare-row"><span>Fallback percentile (practice count)</span><strong>${practicePercentile.toFixed(0)}th</strong></div>` +
            compareHelp +
            compareFooter
        compareCardEl.classList.remove("is-empty")
        return
    }

    const percentile = percentileRank(localValue, allValues)
    const sortedValues = allValues.slice().sort((a, b) => a - b)
    const median = sortedValues[Math.floor(sortedValues.length / 2)]
    const min = sortedValues[0]
    const max = sortedValues[sortedValues.length - 1]
    const direction = compareDirection(metric.key)
    const directionText =
        direction === "lower_better" ? "Lower is better" : "Higher is better"
    const compareHelp = buildCompareHelpHtml(
        metric.label,
        metric.key,
        directionText,
        allValues.length,
    )
    const badge = compareBadge(metric.key, percentile)
    const percentileText = formatOrdinal(percentile)
    const medianNote =
        median === 0
            ? `<div class="compare-note">Many loaded areas have zero for this metric, so small differences can shift percentile.</div>`
            : ""
    let scopeNote = ""
    if (metric.key === "accepting_adults_per_10k_adults") {
        const nearby = countNearbyAcceptingAdults()
        if (nearby) {
            scopeNote =
                `<div class="compare-note">This value is for the selected MSOA area, not a radius around your point. ` +
                `Nearby context: ${nearby.count} accepting NHS adult clinics within ${nearby.radiusKm.toFixed(1)} km.</div>`
        } else {
            scopeNote = `<div class="compare-note">This value is for the selected MSOA area, not a radius around your point.</div>`
        }
    }

    compareCardEl.innerHTML =
        compareHeader +
        `<div class="compare-area">${localArea.area_name}</div>` +
        `<div class="compare-row"><span>Interpretation</span><strong class="compare-pill ${badge.cls}">${badge.label}</strong></div>` +
        `<div class="compare-row"><span>${metric.label}</span><strong>${metric.format(localValue)}</strong></div>` +
        `<div class="compare-row"><span>England range (loaded MSOAs)</span><strong>${metric.format(min)} - ${metric.format(max)}</strong></div>` +
        `<div class="compare-row"><span>England percentile (loaded MSOAs)</span><strong>${percentileText}</strong></div>` +
        `<div class="compare-row"><span>England median</span><strong>${metric.format(median)}</strong></div>` +
        `<div class="compare-note">${directionText} for this metric.</div>` +
        scopeNote +
        medianNote +
        compareHelp +
        compareFooter
    compareCardEl.classList.remove("is-empty")
}

function computeAreaScale() {
    const values = Object.keys(areaMetrics)
        .map((areaCode) => getAreaMetricValue(areaCode))
        .filter((v) => v !== null)

    if (!values.length) {
        return { min: 0, max: 1 }
    }

    return { min: Math.min(...values), max: Math.max(...values) }
}

function computeAreaBreaks() {
    const values = Object.keys(areaMetrics)
        .map((areaCode) => getAreaMetricValue(areaCode))
        .filter((v) => v !== null)
        .sort((a, b) => a - b)

    if (!values.length) {
        return [0, 1]
    }
    if (values.length === 1) {
        return [values[0], values[0]]
    }

    const breaks = []
    const bins = getAreaColors().length
    for (let i = 0; i <= bins; i += 1) {
        const idx = Math.round(((values.length - 1) * i) / bins)
        breaks.push(values[idx])
    }
    return breaks
}

function styleArea(feature) {
    const value = getAreaMetricValue(feature.properties.area_code)
    const coloringOff = areaColorScheme === "off"
    return {
        weight: 0.45,
        color: "#5c6773",
        fillOpacity: coloringOff ? 0.1 : 0.52,
        fillColor: colorForValue(value),
    }
}

function isEnglandAreaCode(areaCode) {
    return typeof areaCode === "string" && areaCode.startsWith("MSOA::E")
}

function highlightArea(event) {
    const layer = event.target
    layer.setStyle({
        weight: 1.2,
        color: "#1f2937",
        fillOpacity: areaColorScheme === "off" ? 0.22 : 0.78,
    })
    const areaCode =
        layer.feature && layer.feature.properties
            ? layer.feature.properties.area_code
            : null
    if (!isEnglandAreaCode(areaCode)) {
        areaInfoControl.update()
        statusEl.textContent = OUTSIDE_ENGLAND_HOVER_WARNING
        statusEl.classList.remove("is-empty")
        return
    }
    if (statusEl.textContent === OUTSIDE_ENGLAND_HOVER_WARNING) {
        if (lastSearchPoint) {
            updateStatusWithResultCount()
        } else {
            statusEl.textContent = ""
            statusEl.classList.add("is-empty")
        }
    }
    areaInfoControl.update(areaCode)
}

function resetAreaHighlight(event) {
    if (areaLayer) {
        areaLayer.resetStyle(event.target)
    }
    areaInfoControl.update()
    if (statusEl.textContent === OUTSIDE_ENGLAND_HOVER_WARNING) {
        if (lastSearchPoint) {
            updateStatusWithResultCount()
        } else {
            statusEl.textContent = ""
            statusEl.classList.add("is-empty")
        }
    }
}

function onAreaClick(event) {
    if (searchMode !== "viewport") {
        return
    }
    const feature =
        event.target && event.target.feature ? event.target.feature : null
    const areaCode =
        feature && feature.properties ? feature.properties.area_code : null
    if (!isEnglandAreaCode(areaCode)) {
        statusEl.textContent = OUTSIDE_ENGLAND_HOVER_WARNING
        statusEl.classList.remove("is-empty")
        return
    }

    forcedCompareAreaCode = areaCode
    forcedOutlineLsoaCode =
        feature && feature.id !== undefined && feature.id !== null
            ? String(feature.id)
            : null
    areaInfoControl.update(areaCode)

    const center = centroidOfFeature(feature)
    if (!center) {
        return
    }
    lastSearchPoint = { lat: center.lat, lon: center.lon }
    lastSearchContext = "Viewport mode."
    map.panTo([center.lat, center.lon])
    updateCompareCard(center.lat, center.lon)
}

function onEachArea(feature, layer) {
    layer.on({
        mouseover: highlightArea,
        mouseout: resetAreaHighlight,
        click: onAreaClick,
    })
}

function renderAreaLayer() {
    if (!areasGeojson || !Object.keys(areaMetrics).length) {
        return
    }

    areaScale = computeAreaScale()
    areaBreaks = computeAreaBreaks()

    if (areaLayer) {
        map.removeLayer(areaLayer)
    }

    const visibleFeatures = selectVisibleAreaFeatures()
    areaLayer = L.geoJSON(
        { type: "FeatureCollection", features: visibleFeatures },
        {
            style: styleArea,
            onEachFeature: onEachArea,
        },
    )

    if (areaOverlayCheckbox.checked) {
        areaLayer.addTo(map)
        areaLayer.bringToBack()
        areaInfoControl.addTo(map)
        legendControl.addTo(map)
        legendControl.update()
    } else {
        map.removeControl(areaInfoControl)
        map.removeControl(legendControl)
    }
}

function clearSelectedAreaOutline() {
    if (!selectedAreaOutlineLayer) {
        return
    }
    map.removeLayer(selectedAreaOutlineLayer)
    selectedAreaOutlineLayer = null
}

function renderSelectedAreaOutline(
    areaCode,
    searchLat = null,
    searchLon = null,
) {
    clearSelectedAreaOutline()
    if (!areasGeojson || !areaCode) {
        return
    }
    const allFeatures = areasGeojson.features || []
    const features = allFeatures.filter(
        (feature) =>
            feature &&
            feature.properties &&
            feature.properties.area_code === areaCode,
    )
    if (!features.length) {
        return
    }

    let selectedFeatures = features
    if (forcedOutlineLsoaCode) {
        const exact = allFeatures.find(
            (feature) =>
                feature &&
                String(feature.id || "") === forcedOutlineLsoaCode &&
                feature.properties &&
                feature.properties.area_code === areaCode,
        )
        if (exact) {
            selectedFeatures = [exact]
        }
    }
    // Show a single local fragment only: exact containing feature, else nearest feature.
    if (!forcedOutlineLsoaCode && searchLat != null && searchLon != null) {
        const containing = features.filter((feature) =>
            featureContainsPoint(feature, searchLat, searchLon),
        )
        if (containing.length) {
            selectedFeatures = [containing[0]]
        } else {
            const withCentroid = features
                .map((feature) => ({
                    feature,
                    centroid: centroidOfFeature(feature),
                }))
                .filter((x) => x.centroid)
            if (withCentroid.length) {
                let best = withCentroid[0]
                let bestD = Number.POSITIVE_INFINITY
                for (const item of withCentroid) {
                    const d = haversineKm(
                        searchLat,
                        searchLon,
                        item.centroid.lat,
                        item.centroid.lon,
                    )
                    if (d < bestD) {
                        bestD = d
                        best = item
                    }
                }
                selectedFeatures = [best.feature]
            }
        }
    }

    selectedAreaOutlineLayer = L.geoJSON(
        { type: "FeatureCollection", features: selectedFeatures },
        {
            interactive: false,
            style: {
                color: "#1d4ed8",
                weight: 2.4,
                opacity: 0.95,
                fillColor: "#3b82f6",
                fillOpacity: 0.06,
            },
        },
    ).addTo(map)
    selectedAreaOutlineLayer.bringToFront()
}

function toggleAreaLayer() {
    if (areaColoringControlsEl) {
        areaColoringControlsEl.classList.toggle(
            "is-empty",
            !areaOverlayCheckbox.checked,
        )
    }
    if (!areaLayer) {
        return
    }
    if (areaOverlayCheckbox.checked) {
        areaLayer.addTo(map)
        areaLayer.bringToBack()
        areaInfoControl.addTo(map)
        legendControl.addTo(map)
        legendControl.update()
    } else {
        map.removeLayer(areaLayer)
        map.removeControl(areaInfoControl)
        map.removeControl(legendControl)
    }
}

function isInEnglandWalesApprox(lat, lon) {
    return (
        lat >= ENGLAND_WALES_BOUNDS.minLat &&
        lat <= ENGLAND_WALES_BOUNDS.maxLat &&
        lon >= ENGLAND_WALES_BOUNDS.minLon &&
        lon <= ENGLAND_WALES_BOUNDS.maxLon
    )
}

function updateCoverageBanner() {
    if (!areaDataLoaded) {
        coverageBannerEl.classList.add("is-empty")
        return
    }
    const center = map.getCenter()
    const hasAreaFeatures = Boolean(
        areasGeojson && areasGeojson.features && areasGeojson.features.length,
    )
    const outsideCoverage =
        !hasAreaFeatures ||
        !findContainingEnglandAreaCodeByPoint(center.lat, center.lng)
    coverageBannerEl.classList.toggle("is-empty", !outsideCoverage)
}

async function loadPractices() {
    const resp = await fetch("data/processed/practices.geojson")
    const geo = await resp.json()
    practices = geo.features.map((f) => ({
        ...f.properties,
        lon: f.geometry.coordinates[0],
        lat: f.geometry.coordinates[1],
    }))
}

async function loadAreaData() {
    const [areasResp, metricsResp] = await Promise.all([
        fetch("data/processed/areas.geojson"),
        fetch("data/processed/area_metrics.json"),
    ])
    if (!areasResp.ok || !metricsResp.ok) {
        throw new Error("Failed to load area overlay data.")
    }
    areasGeojson = await areasResp.json()
    areaMetrics = await metricsResp.json()
    areaFeatureIndex = (areasGeojson.features || [])
        .map((feature) => {
            const bounds = featureBoundsFromGeometry(
                feature && feature.geometry,
            )
            const centroid = centroidOfFeature(feature)
            if (!bounds || !centroid) {
                return null
            }
            return { feature, bounds, centroid }
        })
        .filter((entry) => entry)
    for (const areaCode of Object.keys(areaMetrics)) {
        const area = areaMetrics[areaCode]
        const pressure = Number(area.practices_per_10k) || 0
        const adultsDensity = Number(area.accepting_adults_per_10k_adults) || 0
        const imdDecile = Number(area.imd_decile) || 10
        const pressureGap = Math.max(0, 6 - pressure)
        const adultsGap = Math.max(0, 4 - adultsDensity)
        const deprivationFactor = Math.max(0, 11 - imdDecile) / 10
        area.desert_risk_score = Number(
            (pressureGap + adultsGap + deprivationFactor).toFixed(3),
        )
    }
    areaDataLoaded = true
    renderAreaLayer()
}

async function ensureAreaDataLoaded() {
    if (areaDataLoaded) {
        return
    }
    if (!areaDataLoadPromise) {
        areaDataLoadPromise = loadAreaData().catch((err) => {
            areaDataLoadPromise = null
            throw err
        })
    }
    await areaDataLoadPromise
}

async function geocodePostcode(postcode) {
    const endpoint = `https://api.postcodes.io/postcodes/${encodeURIComponent(postcode)}`
    const resp = await fetch(endpoint)
    if (!resp.ok) {
        throw new Error("Postcode not found")
    }
    const body = await resp.json()
    return {
        lat: body.result.latitude,
        lon: body.result.longitude,
        msoa: body.result.msoa || null,
        msoaCode: (body.result.codes && body.result.codes.msoa) || null,
        lsoaCode: (body.result.codes && body.result.codes.lsoa) || null,
        country: body.result.country || null,
    }
}

async function geocodeAddress(query) {
    const endpoint = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=gb&q=${encodeURIComponent(query)}`
    const resp = await fetch(endpoint, {
        headers: {
            Accept: "application/json",
        },
    })
    if (!resp.ok) {
        throw new Error("Address lookup failed")
    }
    const rows = await resp.json()
    if (!Array.isArray(rows) || !rows.length) {
        throw new Error("Address not found")
    }
    const top = rows[0]
    const lat = Number(top.lat)
    const lon = Number(top.lon)
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        throw new Error("Address lookup failed")
    }
    let country = null
    if (top.address && typeof top.address.country === "string") {
        country = top.address.country
    }
    return {
        lat,
        lon,
        msoa: null,
        msoaCode: null,
        lsoaCode: null,
        country,
    }
}

function updateStatusWithResultCount() {
    if (searchMode === "viewport" && map.getZoom() < VIEWPORT_MIN_ZOOM) {
        statusEl.textContent = `Viewport mode. Zoom in to at least ${VIEWPORT_MIN_ZOOM} to show clinics.`
        statusEl.classList.remove("is-empty")
        return
    }
    let detail = ""
    if (rankedResults.length === 0) {
        detail =
            "Found 0 practices. Try increasing the radius or switch View to 'All practices'."
        statusEl.classList.remove("is-empty")
    } else {
        detail = `Found ${rankedResults.length} practices.`
        statusEl.classList.remove("is-empty")
    }
    const markerLimit = markerLimitForCurrentMode()
    if (rankedResults.length > markerLimit) {
        detail += ` Showing first ${markerLimit} on the map.`
    }
    statusEl.textContent = lastSearchContext
        ? `${lastSearchContext} ${detail}`
        : detail
}

function recomputeAndRenderResults() {
    if (searchMode === "viewport") {
        const center = map.getCenter()
        lastSearchPoint = { lat: center.lat, lon: center.lng }
        lastSearchContext = "Viewport mode."
        if (map.getZoom() < VIEWPORT_MIN_ZOOM) {
            rankedResults = []
            visibleResultCount = 25
            activePracticeId = null
            renderResults()
            renderMarkers(rankedResults)
            updateDentalDesertBanner()
            updateStatusWithResultCount()
            updateCompareCard(lastSearchPoint.lat, lastSearchPoint.lon)
            updateRadiusCircle()
            return
        }
        rankedResults = buildViewportResults()
    } else {
        if (!lastSearchPoint) {
            return
        }
        rankedResults = buildRankedResults(
            lastSearchPoint.lat,
            lastSearchPoint.lon,
        )
    }
    visibleResultCount = 25
    activePracticeId = rankedResults[0] ? rankedResults[0].practice_id : null
    renderResults()
    renderMarkers(rankedResults)
    updateDentalDesertBanner()
    updateStatusWithResultCount()
    updateCompareCard(lastSearchPoint.lat, lastSearchPoint.lon)
    updateRadiusCircle()
}

function runSearchFromPoint(lat, lon, contextLabel, keepCurrentZoom = false) {
    lastSearchPoint = { lat, lon }
    lastSearchContext = contextLabel

    map.setView([lat, lon], keepCurrentZoom ? map.getZoom() : 11)
    if (userMarker) {
        map.removeLayer(userMarker)
    }
    userMarker = L.circleMarker([lat, lon], {
        radius: 7,
        color: "#2b6cb0",
        weight: 2,
        fillColor: "#5fa8ff",
        fillOpacity: 0.35,
    })
        .addTo(map)
        .bindPopup(contextLabel || "Search location")

    rankedResults = buildRankedResults(lat, lon)
    visibleResultCount = 25
    activePracticeId = rankedResults[0] ? rankedResults[0].practice_id : null

    renderResults()
    renderMarkers(rankedResults)
    updateDentalDesertBanner()
    updateStatusWithResultCount()
    updateCompareCard(lat, lon)
    updateRadiusCircle()
}

function setSearchMode(nextMode) {
    searchMode = nextMode
    const isRadius = nextMode === "radius"
    searchModeRadiusButton.classList.toggle("active", isRadius)
    searchModeViewportButton.classList.toggle("active", !isRadius)
    postcodeControlsEl.classList.toggle("is-empty", !isRadius)
    radiusControlsEl.classList.toggle("is-empty", !isRadius)
    searchButton.classList.toggle("is-empty", !isRadius)
    viewportHintEl.classList.toggle("is-empty", isRadius)
    updateResultsTitle()

    if (!isRadius) {
        forcedCompareAreaCode = null
        forcedOutlineLsoaCode = null
        if (userMarker) {
            map.removeLayer(userMarker)
            userMarker = null
        }
        clearSelectedAreaOutline()
        statusEl.textContent = `Viewport mode enabled. Zoom in to at least ${VIEWPORT_MIN_ZOOM} to show clinics.`
        statusEl.classList.remove("is-empty")
        recomputeAndRenderResults()
    }
    updateRadiusCircle()
    saveUiPreferences()
}

function resetView() {
    forcedCompareAreaCode = null
    forcedOutlineLsoaCode = null
    clearSelectedAreaOutline()
    if (userMarker) {
        map.removeLayer(userMarker)
        userMarker = null
    }
    map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM)
    if (searchMode === "viewport") {
        statusEl.textContent = "Viewport reset to default map view."
        statusEl.classList.remove("is-empty")
        recomputeAndRenderResults()
    }
    updateCoverageBanner()
    if (areaOverlayCheckbox.checked && areaDataLoaded) {
        renderAreaLayer()
    }
}

async function runSearch() {
    if (searchMode !== "radius") {
        return
    }
    const raw = postcodeInput.value
    const query = normalizeQuery(raw)
    if (!query) {
        statusEl.textContent = "Enter a postcode or address."
        return
    }

    statusEl.textContent = "Searching..."

    try {
        const looksPostcode = isLikelyUkPostcode(query)
        const normalizedPostcode = normalizePostcode(query)
        const { lat, lon, msoa, msoaCode, country } = looksPostcode
            ? await geocodePostcode(normalizedPostcode)
            : await geocodeAddress(query)
        forcedCompareAreaCode = null
        forcedOutlineLsoaCode = null
        if (msoaCode) {
            const codeKey = `MSOA::${msoaCode}`
            if (areaMetrics[codeKey]) {
                forcedCompareAreaCode = codeKey
            }
        }
        if (!forcedCompareAreaCode && msoa) {
            const key = `MSOA::${msoa}`
            if (areaMetrics[key]) {
                forcedCompareAreaCode = key
            }
        }
        localStorage.setItem("last_postcode", query)
        runSearchFromPoint(
            lat,
            lon,
            looksPostcode
                ? `Postcode ${normalizedPostcode}.`
                : `Address ${query}.`,
        )
        if (typeof country === "string" && country.toLowerCase() === "wales") {
            const base = statusEl.textContent || ""
            const warning =
                "Coverage note: Wales practice data is currently limited and may be incomplete."
            statusEl.textContent = base ? `${base} ${warning}` : warning
            statusEl.classList.remove("is-empty")
        }
    } catch (err) {
        statusEl.textContent =
            err instanceof Error ? err.message : "Search failed."
        statusEl.classList.remove("is-empty")
        desertBannerEl.textContent = ""
        desertBannerEl.classList.add("is-empty")
        compareCardEl.textContent = ""
        compareCardEl.classList.add("is-empty")
        clearSelectedAreaOutline()
        forcedCompareAreaCode = null
        forcedOutlineLsoaCode = null
    }
}

searchButton.addEventListener("click", runSearch)
postcodeInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        runSearch()
    }
})
loadMoreButton.addEventListener("click", () => {
    visibleResultCount += 25
    renderResults()
})
radiusSelect.addEventListener("input", () => {
    updateRadiusDisplay()
    recomputeAndRenderResults()
    saveUiPreferences()
})
modeSelect.addEventListener("change", () => {
    recomputeAndRenderResults()
    saveUiPreferences()
})
searchModeRadiusButton.addEventListener("click", () => setSearchMode("radius"))
searchModeViewportButton.addEventListener("click", () => {
    forcedCompareAreaCode = null
    forcedOutlineLsoaCode = null
    setSearchMode("viewport")
})
if (resetViewButton) {
    resetViewButton.addEventListener("click", resetView)
}
areaOverlayCheckbox.addEventListener("change", async () => {
    if (areaColoringControlsEl) {
        areaColoringControlsEl.classList.toggle(
            "is-empty",
            !areaOverlayCheckbox.checked,
        )
    }
    if (areaOverlayCheckbox.checked && !areaDataLoaded) {
        statusEl.textContent = "Loading area overlay..."
        statusEl.classList.remove("is-empty")
        try {
            await ensureAreaDataLoaded()
            statusEl.textContent = ""
            statusEl.classList.add("is-empty")
            if (lastSearchPoint) {
                updateCompareCard(lastSearchPoint.lat, lastSearchPoint.lon)
            }
            updateCoverageBanner()
        } catch (err) {
            areaOverlayCheckbox.checked = false
            if (areaColoringControlsEl) {
                areaColoringControlsEl.classList.add("is-empty")
            }
            statusEl.textContent =
                err instanceof Error ? err.message : "Area overlay load failed."
            statusEl.classList.remove("is-empty")
            updateCoverageBanner()
            return
        }
    }
    saveUiPreferences()
    toggleAreaLayer()
})
areaMetricSelect.addEventListener("change", () => {
    renderAreaLayer()
    if (lastSearchPoint) {
        updateCompareCard(lastSearchPoint.lat, lastSearchPoint.lon)
    }
    saveUiPreferences()
})
if (areaColoringSelect) {
    areaColoringSelect.addEventListener("change", () => {
        areaColorScheme = areaColoringSelect.value || "contrast"
        renderAreaLayer()
        saveUiPreferences()
    })
}
map.on("moveend", () => {
    if (searchMode === "viewport") {
        recomputeAndRenderResults()
    }
    updateCoverageBanner()
    if (areaOverlayCheckbox.checked && areaDataLoaded) {
        renderAreaLayer()
    }
})
;(async () => {
    restoreUiPreferences()
    await Promise.all([loadPractices(), loadSnapshotDate()])
    loadMoreButton.style.display = "none"
    statusEl.classList.add("is-empty")
    desertBannerEl.textContent = ""
    desertBannerEl.classList.add("is-empty")
    compareCardEl.textContent = ""
    compareCardEl.classList.add("is-empty")
    clearSelectedAreaOutline()
    resultsEl.classList.add("is-empty")
    resultsEmptyEl.classList.remove("is-empty")
    setSearchMode(searchMode)
    updateRadiusDisplay()
    updateResultsTitle()
    updateCoverageBanner()
    if (areaOverlayCheckbox.checked) {
        areaOverlayCheckbox.dispatchEvent(new Event("change"))
    }
    const last = localStorage.getItem("last_postcode")
    if (last) {
        postcodeInput.value = last
    }
})()
