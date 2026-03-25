<template>
  <div id="app">
    <header class="app-header">
      <div class="header-content">
        <h1>Insect AI Dataset Gallery</h1>
        <p class="subtitle">BioTrove + GBIF | {{ summary.total_images?.toLocaleString() }} images | {{ Object.keys(summary.orders || {}).length }} orders | {{ Object.keys(summary.families || {}).length }} families</p>
      </div>
    </header>

    <div class="controls">
      <div class="filters">
        <div class="filter-group">
          <label>Order</label>
          <select v-model="selectedOrder" @change="selectedFamily = ''">
            <option value="">All Orders ({{ Object.keys(summary.orders || {}).length }})</option>
            <option v-for="(count, order) in sortedOrders" :key="order" :value="order">
              {{ order }} ({{ count.toLocaleString() }})
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Family</label>
          <select v-model="selectedFamily">
            <option value="">All Families</option>
            <option v-for="(count, fam) in availableFamilies" :key="fam" :value="fam">
              {{ fam }} ({{ count.toLocaleString() }})
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Source</label>
          <select v-model="selectedSource">
            <option value="">All Sources</option>
            <option value="biotrove">BioTrove</option>
            <option value="gbif">GBIF (gap-fill)</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Curation</label>
          <select v-model="selectedCuration">
            <option value="">All</option>
            <option value="keep">Keep ({{ curationCounts.keep || 0 }})</option>
            <option value="drop">All Dropped ({{ curationCounts.drop || 0 }})</option>
            <option value="drop_larva">Larvae ({{ curationCounts.drop_larva || 0 }})</option>
            <option value="drop_pupa">Pupae ({{ curationCounts.drop_pupa || 0 }})</option>
            <option value="drop_habitat">Habitat shots ({{ curationCounts.drop_habitat || 0 }})</option>
            <option value="drop_quality">Low quality ({{ curationCounts.drop_quality || 0 }})</option>
            <option value="drop_not_insect">Not insect ({{ curationCounts.drop_not_insect || 0 }})</option>
            <option value="drop_multiple">Multiple ({{ curationCounts.drop_multiple || 0 }})</option>
            <option value="drop_dead">Dead/damaged ({{ curationCounts.drop_dead || 0 }})</option>
            <option value="review">Needs Review ({{ curationCounts.review || 0 }})</option>
            <option value="not_curated">Not Curated ({{ curationCounts.not_curated || 0 }})</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Search</label>
          <input type="text" v-model="searchText" placeholder="Species, genus..." />
        </div>
      </div>

      <div class="results-bar">
        <span>{{ filteredImages.length.toLocaleString() }} of {{ dataset.length.toLocaleString() }} images (sampled from {{ summary.total_images?.toLocaleString() }})</span>
        <div class="view-controls">
          <button :class="{active: viewMode === 'grid'}" @click="viewMode = 'grid'">Grid</button>
          <button :class="{active: viewMode === 'table'}" @click="viewMode = 'table'">Table</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading dataset...</div>
    <div v-else-if="dataset.length < (summary.sampled_images || 0)" class="loading-progress">
      Loading images: {{ dataset.length.toLocaleString() }} / {{ (summary.sampled_images || 0).toLocaleString() }}
    </div>

    <div v-else-if="viewMode === 'grid'" class="image-grid">
      <div v-for="img in visibleImages" :key="img.id" class="image-card" :class="cardClass(img)">
        <div class="image-wrapper" @click="openModal(img)">
          <img :src="img.thumbnail_url" :alt="img.scientific_name || img.family" loading="lazy" @error="onImgError($event)" />
          <div v-if="img.curation_status && img.curation_status !== 'not_curated'" class="curation-badge" :class="img.curation_status">
            {{ badgeText(img.curation_status) }}
          </div>
        </div>
        <div class="card-info">
          <div class="taxon-line">
            <span class="order-tag">{{ img.order }}</span>
            <span class="family-name">{{ img.family }}</span>
          </div>
          <div v-if="img.scientific_name" class="species-name">{{ img.scientific_name }}</div>
          <div v-if="img.common_name" class="common-name">{{ img.common_name }}</div>
          <div v-if="img.curation_issues" class="issues">{{ img.curation_issues }}</div>
        </div>
      </div>
    </div>

    <div v-else class="table-view">
      <table>
        <thead>
          <tr>
            <th>Image</th>
            <th @click="sortBy('order')">Order</th>
            <th @click="sortBy('family')">Family</th>
            <th @click="sortBy('scientific_name')">Species</th>
            <th>Source</th>
            <th @click="sortBy('curation_status')">Curation</th>
            <th>Issues</th>
            <th>Life Stage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="img in visibleImages" :key="img.id" :class="cardClass(img)" @click="openModal(img)">
            <td><img :src="img.thumbnail_url" class="table-thumb" loading="lazy" @error="onImgError($event)" /></td>
            <td>{{ img.order }}</td>
            <td>{{ img.family }}</td>
            <td><em>{{ img.scientific_name }}</em></td>
            <td><span class="source-tag" :class="img.source">{{ img.source }}</span></td>
            <td><span class="curation-tag" :class="img.curation_status">{{ img.curation_status }}</span></td>
            <td>{{ img.curation_issues || '' }}</td>
            <td>{{ img.life_stage || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="visibleCount < filteredImages.length" class="load-more">
      <button @click="visibleCount += 100">Load More ({{ (filteredImages.length - visibleCount).toLocaleString() }} remaining)</button>
    </div>

    <div v-if="modalImage" class="modal-overlay" @click.self="modalImage = null">
      <div class="modal-content">
        <button class="modal-close" @click="modalImage = null">&times;</button>
        <img :src="modalImage.url" :alt="modalImage.scientific_name" />
        <div class="modal-info">
          <h3>{{ modalImage.scientific_name || `${modalImage.order}: ${modalImage.family}` }}</h3>
          <p v-if="modalImage.common_name">{{ modalImage.common_name }}</p>
          <table class="modal-meta">
            <tr><td>Order</td><td>{{ modalImage.order }}</td></tr>
            <tr><td>Family</td><td>{{ modalImage.family }}</td></tr>
            <tr v-if="modalImage.genus"><td>Genus</td><td>{{ modalImage.genus }}</td></tr>
            <tr v-if="modalImage.species"><td>Species</td><td>{{ modalImage.species }}</td></tr>
            <tr><td>Source</td><td>{{ modalImage.source }}</td></tr>
            <tr><td>Curation</td><td>{{ modalImage.curation_status }}</td></tr>
            <tr v-if="modalImage.curation_issues"><td>Issues</td><td>{{ modalImage.curation_issues }}</td></tr>
            <tr v-if="modalImage.life_stage"><td>Life Stage</td><td>{{ modalImage.life_stage }}</td></tr>
            <tr v-if="modalImage.curation_confidence"><td>Confidence</td><td>{{ modalImage.curation_confidence }}</td></tr>
            <tr><td>ID</td><td>{{ modalImage.id }}</td></tr>
          </table>
          <a :href="modalImage.url" target="_blank" class="view-full">View Full Image</a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const dataset = ref([])
const summary = ref({})
const loading = ref(true)
const selectedOrder = ref('')
const selectedFamily = ref('')
const selectedSource = ref('')
const selectedCuration = ref('')
const searchText = ref('')
const viewMode = ref('grid')
const visibleCount = ref(100)
const modalImage = ref(null)
const sortField = ref('')
const sortAsc = ref(true)

onMounted(async () => {
  try {
    // Load summary first (tiny, instant)
    const summaryRes = await fetch(import.meta.env.BASE_URL + 'data/dataset_summary.json')
    summary.value = await summaryRes.json()

    // Stream dataset in chunks so UI renders progressively
    const dataRes = await fetch(import.meta.env.BASE_URL + 'data/dataset.json')
    const text = await dataRes.text()
    const allData = JSON.parse(text)

    // Load in batches of 2000 with microtask yields
    const BATCH = 2000
    for (let i = 0; i < allData.length; i += BATCH) {
      dataset.value.push(...allData.slice(i, i + BATCH))
      if (i === 0) loading.value = false  // Show first batch immediately
      if (i + BATCH < allData.length) {
        await new Promise(r => setTimeout(r, 0))  // Yield to render
      }
    }
  } catch (e) {
    console.error('Failed to load dataset:', e)
  }
  loading.value = false
})

const sortedOrders = computed(() => {
  const o = summary.value.orders || {}
  return Object.fromEntries(Object.entries(o).sort((a, b) => b[1] - a[1]))
})

const availableFamilies = computed(() => {
  if (!selectedOrder.value) return {}
  const fbo = summary.value.families_by_order || {}
  return fbo[selectedOrder.value] || {}
})

const curationCounts = computed(() => {
  const counts = {}
  for (const img of dataset.value) {
    const status = img.curation_status || 'not_curated'
    const issue = img.curation_issues || ''
    // Count by specific drop reason
    if (issue.startsWith('drop_')) {
      counts[issue] = (counts[issue] || 0) + 1
      counts.drop = (counts.drop || 0) + 1
    } else if (status.includes('drop')) {
      counts.drop = (counts.drop || 0) + 1
    } else if (status.includes('keep') && status !== 'not_curated') {
      counts.keep = (counts.keep || 0) + 1
    } else if (status.includes('review')) {
      counts.review = (counts.review || 0) + 1
    } else {
      counts.not_curated = (counts.not_curated || 0) + 1
    }
  }
  return counts
})

const filteredImages = computed(() => {
  let imgs = dataset.value
  if (selectedOrder.value) imgs = imgs.filter(i => i.order === selectedOrder.value)
  if (selectedFamily.value) imgs = imgs.filter(i => i.family === selectedFamily.value)
  if (selectedSource.value) imgs = imgs.filter(i => i.source === selectedSource.value)
  if (selectedCuration.value) {
    const v = selectedCuration.value
    if (v === 'drop') {
      imgs = imgs.filter(i => (i.curation_status || '').includes('drop'))
    } else if (v === 'keep') {
      imgs = imgs.filter(i => (i.curation_status || '').includes('keep') && i.curation_status !== 'not_curated')
    } else if (v === 'review') {
      imgs = imgs.filter(i => (i.curation_status || '').includes('review'))
    } else if (v === 'not_curated') {
      imgs = imgs.filter(i => !i.curation_status || i.curation_status === 'not_curated')
    } else if (v.startsWith('drop_')) {
      // Specific drop reason (drop_larva, drop_habitat, etc.)
      imgs = imgs.filter(i => i.curation_issues === v)
    } else {
      imgs = imgs.filter(i => i.curation_status === v)
    }
  }
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    imgs = imgs.filter(i =>
      (i.scientific_name || '').toLowerCase().includes(q) ||
      (i.common_name || '').toLowerCase().includes(q) ||
      (i.genus || '').toLowerCase().includes(q) ||
      (i.family || '').toLowerCase().includes(q)
    )
  }
  if (sortField.value) {
    imgs = [...imgs].sort((a, b) => {
      const va = (a[sortField.value] || '').toString()
      const vb = (b[sortField.value] || '').toString()
      return sortAsc.value ? va.localeCompare(vb) : vb.localeCompare(va)
    })
  }
  return imgs
})

const visibleImages = computed(() => filteredImages.value.slice(0, visibleCount.value))

function sortBy(field) {
  if (sortField.value === field) sortAsc.value = !sortAsc.value
  else { sortField.value = field; sortAsc.value = true }
}

function cardClass(img) {
  if (img.curation_status && img.curation_status.includes('drop')) return 'card-drop'
  if (img.curation_status && img.curation_status.includes('review')) return 'card-review'
  return ''
}

function badgeText(status) {
  if (status.includes('drop')) return 'DROP'
  if (status.includes('review')) return 'REVIEW'
  if (status.includes('keep') && status !== 'not_curated') return 'OK'
  return ''
}

function openModal(img) { modalImage.value = img }

function onImgError(e) {
  e.target.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect fill="#eee" width="200" height="200"/><text x="50%" y="50%" text-anchor="middle" fill="#999" font-size="14">Image unavailable</text></svg>')
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f0; color: #333; }

.app-header { background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 100%); color: white; padding: 1.5rem 2rem; text-align: center; }
.app-header h1 { font-size: 1.8rem; font-weight: 700; }
.subtitle { opacity: 0.85; font-size: 0.9rem; margin-top: 0.3rem; }

.controls { padding: 1rem 2rem; background: white; border-bottom: 1px solid #ddd; position: sticky; top: 0; z-index: 10; }
.filters { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: end; }
.filter-group { display: flex; flex-direction: column; gap: 0.2rem; }
.filter-group label { font-size: 0.75rem; font-weight: 600; color: #666; text-transform: uppercase; }
.filter-group select, .filter-group input { padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; min-width: 140px; background: white; }
.results-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem; font-size: 0.85rem; color: #666; }
.view-controls { display: flex; gap: 0.25rem; }
.view-controls button { padding: 0.3rem 0.8rem; border: 1px solid #ccc; background: white; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.view-controls button.active { background: #2d6a4f; color: white; border-color: #2d6a4f; }

.loading { text-align: center; padding: 3rem; font-size: 1.2rem; color: #666; }
.loading-progress { text-align: center; padding: 0.5rem; font-size: 0.8rem; color: #999; background: #f8f8f8; }

.image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; padding: 1.5rem 2rem; }
.image-card { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: transform 0.2s, box-shadow 0.2s; }
.image-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.image-card.card-drop { border: 2px solid #dc3545; }
.image-card.card-review { border: 2px solid #ffc107; }

.image-wrapper { position: relative; aspect-ratio: 1; overflow: hidden; cursor: pointer; background: #f0f0f0; }
.image-wrapper img { width: 100%; height: 100%; object-fit: cover; }

.curation-badge { position: absolute; top: 0.4rem; right: 0.4rem; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700; color: white; }
.curation-badge.audited_keep, .curation-badge.curated_keep { background: #28a745; }
.curation-badge.audited_drop, .curation-badge.curated_drop { background: #dc3545; }
.curation-badge.audited_review, .curation-badge.curated_review { background: #ffc107; color: #333; }

.card-info { padding: 0.5rem 0.6rem; }
.taxon-line { display: flex; gap: 0.4rem; align-items: center; }
.order-tag { background: #e8f5e9; color: #2d6a4f; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 600; }
.family-name { font-size: 0.85rem; font-weight: 600; }
.species-name { font-style: italic; font-size: 0.8rem; color: #555; margin-top: 0.15rem; }
.common-name { font-size: 0.75rem; color: #888; }
.issues { font-size: 0.7rem; color: #dc3545; margin-top: 0.2rem; font-weight: 500; }

.table-view { padding: 1rem 2rem; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: white; font-size: 0.85rem; }
thead th { background: #2d6a4f; color: white; padding: 0.5rem; text-align: left; cursor: pointer; }
tbody tr { border-bottom: 1px solid #eee; cursor: pointer; }
tbody tr:hover { background: #f0f8f0; }
tbody tr.card-drop { background: #fff0f0; }
tbody tr.card-review { background: #fff8e1; }
td { padding: 0.4rem 0.5rem; }
.table-thumb { width: 50px; height: 50px; object-fit: cover; border-radius: 4px; }
.source-tag { padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.75rem; }
.source-tag.biotrove { background: #e3f2fd; color: #1565c0; }
.source-tag.gbif { background: #fce4ec; color: #c62828; }
.curation-tag { padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.75rem; }

.load-more { text-align: center; padding: 2rem; }
.load-more button { padding: 0.6rem 2rem; background: #2d6a4f; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.load-more button:hover { background: #1a472a; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 2rem; }
.modal-content { background: white; border-radius: 12px; max-width: 900px; max-height: 90vh; overflow-y: auto; display: flex; flex-direction: column; position: relative; }
.modal-close { position: absolute; top: 1rem; right: 1rem; background: rgba(0,0,0,0.5); color: white; border: none; font-size: 1.5rem; width: 2rem; height: 2rem; border-radius: 50%; cursor: pointer; z-index: 10; }
.modal-content > img { width: 100%; max-height: 60vh; object-fit: contain; background: #f5f5f5; }
.modal-info { padding: 1.5rem; }
.modal-info h3 { font-size: 1.2rem; margin-bottom: 0.3rem; }
.modal-meta { margin-top: 0.75rem; font-size: 0.9rem; }
.modal-meta td { padding: 0.2rem 0.5rem; }
.modal-meta td:first-child { font-weight: 600; color: #666; }
.view-full { display: inline-block; margin-top: 1rem; padding: 0.4rem 1rem; background: #2d6a4f; color: white; text-decoration: none; border-radius: 4px; }

@media (max-width: 768px) {
  .filters { flex-direction: column; }
  .filter-group select, .filter-group input { width: 100%; }
  .image-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); padding: 0.75rem; }
}
</style>
