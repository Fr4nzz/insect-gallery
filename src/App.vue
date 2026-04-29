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
          <label>YOLO v12 conf</label>
          <select v-model="selectedYolo">
            <option value="">All</option>
            <option value="kept">≥ threshold (kept)</option>
            <option value="low">below threshold</option>
            <option value="missing">no YOLO result</option>
          </select>
        </div>

        <div class="filter-group">
          <label>SAM3 conf</label>
          <select v-model="selectedSam3">
            <option value="">All</option>
            <option value="kept">≥ threshold (kept)</option>
            <option value="low">below threshold</option>
            <option value="missing">no SAM3 result</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Curation model</label>
          <select v-model="selectedModel">
            <option value="">All models</option>
            <option value="flash">Flash only (Pro never reviewed)</option>
            <option value="pro_any">Pro reviewed (any verdict)</option>
            <option value="pro_rescued">Pro rescued (drop → keep)</option>
            <option value="pro_confirmed_drop">Pro confirmed drop</option>
            <option value="pro_relabeled">Pro changed drop reason</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Pro verdict</label>
          <select v-model="selectedProVerdict">
            <option value="">Any</option>
            <option value="keep">Pro said keep</option>
            <option value="drop_larva">Pro said drop_larva</option>
            <option value="drop_pupa">Pro said drop_pupa</option>
            <option value="drop_habitat">Pro said drop_habitat</option>
            <option value="drop_quality">Pro said drop_quality</option>
            <option value="drop_not_insect">Pro said drop_not_insect</option>
            <option value="drop_multiple">Pro said drop_multiple</option>
            <option value="drop_dead">Pro said drop_dead</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Gemini v3</label>
          <select v-model="selectedV3">
            <option value="">Any</option>
            <option value="keep">v3 keep</option>
            <option value="any_drop">v3 any drop</option>
            <option value="drop_quality">v3 drop_quality</option>
            <option value="drop_larva">v3 drop_larva</option>
            <option value="drop_multiple">v3 drop_multiple</option>
            <option value="drop_habitat">v3 drop_habitat</option>
            <option value="drop_not_insect">v3 drop_not_insect</option>
            <option value="drop_pupa">v3 drop_pupa</option>
            <option value="drop_dead">v3 drop_dead</option>
            <option value="rescue">v3 RESCUE (v1 drop → v3 keep)</option>
            <option value="v3_dropped_v1_keep">v3 dropped a v1 keep</option>
            <option value="v3_use_yolo_true">v3 keep + use YOLO crop</option>
            <option value="v3_use_yolo_false">v3 keep + use FULL image</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Claude smoke-test</label>
          <select v-model="selectedClaude">
            <option value="">Any</option>
            <option value="any">Has Claude smoke-test data (45 imgs)</option>
            <option value="efforts_differ">Claude efforts disagree</option>
            <option value="claude_rescue">Claude RESCUE (v1 drop → claude keep)</option>
            <option value="claude_dropped_v1_keep">Claude dropped a v1 keep</option>
            <option value="claude_drop_any">Claude any drop (medium effort)</option>
            <option value="claude_drop_other">Claude drop_other (custom reason)</option>
            <option value="claude_keep_all">Claude keep at all 3 efforts</option>
            <option value="claude_use_yolo_true">Claude keep + use YOLO crop</option>
            <option value="claude_use_yolo_false">Claude keep + use FULL image</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Gemini 3.1 Pro</label>
          <select v-model="selectedGeminiPro">
            <option value="">Any</option>
            <option value="any">Has Gemini Pro data (300 imgs)</option>
            <option value="claude_vs_gp_disagree">Claude vs Gemini Pro disagree</option>
            <option value="gp_keep_claude_drop">Gemini Pro keep, Claude dropped</option>
            <option value="gp_drop_claude_keep">Gemini Pro dropped, Claude kept</option>
            <option value="gp_dead">Gemini Pro = dead</option>
            <option value="gp_multiple">Gemini Pro = multiple</option>
            <option value="gp_quality">Gemini Pro = quality</option>
            <option value="gp_larva">Gemini Pro = larva</option>
            <option value="gp_other">Gemini Pro = other</option>
          </select>
        </div>

        <div class="filter-group">
          <label>Codex</label>
          <select v-model="selectedCodex">
            <option value="">Any</option>
            <option value="any">Has Codex data (45 imgs)</option>
            <option value="combos_differ">Codex combos disagree</option>
            <option value="claude_vs_codex">Claude vs Codex disagree (gpt-5.4 medium)</option>
            <option value="codex_drop_other">Codex drop_other (any combo)</option>
            <option value="codex_keep_all">Codex keep at all 6 combos</option>
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
          <div v-if="img.pro_reviewed" class="pro-badge"
               :class="{
                 rescued: img.pro_outcome === 'rescued',
                 confirmed: img.pro_outcome === 'confirmed_drop',
                 relabeled: img.pro_outcome === 'relabeled_drop',
               }"
               :title="proBadgeTitle(img)">
            {{ proBadgeLabel(img) }}
          </div>
          <div v-if="img.yolo_confidence !== null && img.yolo_confidence !== undefined" class="yolo-badge"
               :class="{ low: img.yolo_kept === false }"
               :title="`YOLO v12 insect detection confidence: ${(img.yolo_confidence*100).toFixed(0)}%`">
            Y12 {{ (img.yolo_confidence*100).toFixed(0) }}%
          </div>
          <div v-if="img.sam3_confidence !== null && img.sam3_confidence !== undefined" class="sam3-badge"
               :class="{ low: img.sam3_kept === false }"
               :title="`SAM3 insect confidence: ${(img.sam3_confidence*100).toFixed(0)}%`">
            S3 {{ (img.sam3_confidence*100).toFixed(0) }}%
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

    <div v-if="modalImage" class="modal-overlay" @click.self="closeModal()">
      <div class="modal-content">
        <button class="modal-close" @click="closeModal()">&times;</button>
        <div class="modal-image-wrap">
          <img :src="modalImage.url" :alt="modalImage.scientific_name"
               @load="onModalImgLoad" />
          <svg
            v-if="showBboxOverlay && modalImgNatural && hasYoloBbox(modalImage)"
            class="bbox-overlay"
            :viewBox="`0 0 ${modalImgNatural.w} ${modalImgNatural.h}`"
            preserveAspectRatio="xMidYMid meet"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect
              v-for="(d, i) in (modalImage.yolo_other_dets || [])"
              :key="'o' + i"
              :x="d.xyxy[0]"
              :y="d.xyxy[1]"
              :width="d.xyxy[2] - d.xyxy[0]"
              :height="d.xyxy[3] - d.xyxy[1]"
              class="bbox-other"
            />
            <rect
              v-if="modalImage.yolo_bbox"
              :x="modalImage.yolo_bbox[0]"
              :y="modalImage.yolo_bbox[1]"
              :width="modalImage.yolo_bbox[2] - modalImage.yolo_bbox[0]"
              :height="modalImage.yolo_bbox[3] - modalImage.yolo_bbox[1]"
              :class="['bbox-best', modalImage.yolo_kept ? 'bbox-kept' : 'bbox-dropped']"
            />
            <text
              v-if="modalImage.yolo_bbox && modalImage.yolo_confidence !== null && modalImage.yolo_confidence !== undefined"
              :x="modalImage.yolo_bbox[0]"
              :y="Math.max(modalImage.yolo_bbox[1] - bboxFontSize * 0.4, bboxFontSize)"
              :font-size="bboxFontSize"
              :class="['bbox-label', modalImage.yolo_kept ? 'bbox-kept' : 'bbox-dropped']"
            >
              YOLO {{ (modalImage.yolo_confidence * 100).toFixed(0) }}%
            </text>
          </svg>
          <div v-if="hasYoloVerdict(modalImage)" class="bbox-toggle">
            <label>
              <input type="checkbox" v-model="showBboxOverlay" />
              Show YOLO bboxes
            </label>
            <span v-if="modalImage.yolo_reason === 'no_detection'" class="bbox-flag bbox-flag-none">
              YOLO saw no insect
            </span>
            <span v-else-if="modalImage.yolo_reason === 'below_threshold'" class="bbox-flag bbox-flag-low">
              YOLO low-confidence ({{ (modalImage.yolo_confidence * 100).toFixed(0) }}%)
            </span>
            <span v-else-if="modalImage.yolo_kept" class="bbox-flag bbox-flag-kept">
              YOLO kept ({{ (modalImage.yolo_confidence * 100).toFixed(0) }}%)
            </span>
          </div>
        </div>
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
            <tr v-if="modalImage.curation_model">
              <td>Curation model</td>
              <td>{{ modalImage.curation_model }}</td>
            </tr>
            <tr v-if="modalImage.curation_confidence"><td>Gemini conf</td><td>{{ modalImage.curation_confidence }}</td></tr>
            <tr v-if="modalImage.pro_reviewed">
              <td>Pro outcome</td>
              <td>
                <span v-if="modalImage.pro_outcome === 'rescued'" style="color:#28a745; font-weight:600">
                  RESCUED — Flash had labeled "{{ modalImage.flash_label_was }}"
                </span>
                <span v-else-if="modalImage.pro_outcome === 'confirmed_drop'">
                  Confirmed drop "{{ modalImage.pro_label }}" (Flash also said "{{ modalImage.flash_label_was }}")
                </span>
                <span v-else-if="modalImage.pro_outcome === 'relabeled_drop'">
                  Relabeled: Flash said "{{ modalImage.flash_label_was }}" → Pro said "{{ modalImage.pro_label }}"
                </span>
                <span v-else>Reviewed</span>
              </td>
            </tr>
            <tr v-if="modalImage.pro_confidence !== null && modalImage.pro_confidence !== undefined">
              <td>Pro conf</td>
              <td>{{ modalImage.pro_confidence }}</td>
            </tr>
            <tr v-if="modalImage.pro_reason">
              <td>Pro reason</td>
              <td><em>{{ modalImage.pro_reason }}</em></td>
            </tr>
            <tr v-if="modalImage.yolo_confidence !== null && modalImage.yolo_confidence !== undefined">
              <td>YOLO v12 conf</td>
              <td>{{ (modalImage.yolo_confidence * 100).toFixed(1) }}%
                  <span v-if="modalImage.yolo_kept">— kept for training</span>
                  <span v-else>— sent to OOD pool</span>
              </td>
            </tr>
            <tr v-if="modalImage.yolo_reason">
              <td>YOLO verdict</td>
              <td>
                <span v-if="modalImage.yolo_reason === 'no_detection'">No detection</span>
                <span v-else-if="modalImage.yolo_reason === 'below_threshold'">Below threshold</span>
                <span v-else>{{ modalImage.yolo_reason }}</span>
              </td>
            </tr>
            <tr v-if="modalImage.yolo_gemini_label && modalImage.yolo_gemini_label !== modalImage.curation_status">
              <td>Gemini × YOLO</td>
              <td>
                <span v-if="modalImage.yolo_gemini_label === 'keep' && modalImage.yolo_kept" style="color:#28a745">both keep</span>
                <span v-else-if="modalImage.yolo_gemini_label === 'keep' && !modalImage.yolo_kept" style="color:#d97706">Gemini keep / YOLO drop</span>
                <span v-else-if="modalImage.yolo_gemini_label && modalImage.yolo_gemini_label.startsWith('drop') && modalImage.yolo_kept" style="color:#0ea5e9; font-weight:600">YOLO RESCUE — Gemini said {{ modalImage.yolo_gemini_label }}</span>
                <span v-else>both drop ({{ modalImage.yolo_gemini_label }})</span>
              </td>
            </tr>
            <tr v-if="modalImage.v3_label">
              <td colspan="2" style="background:#eef2ff; padding:0.5rem; font-weight:700; color:#3730a3">
                Gemini v3 (with YOLO context)
              </td>
            </tr>
            <tr v-if="modalImage.v3_label">
              <td>v3 verdict</td>
              <td>
                <span v-if="modalImage.v3_label === 'keep'" style="color:#15803d; font-weight:600">KEEP</span>
                <span v-else style="color:#b91c1c; font-weight:600">{{ modalImage.v3_label.toUpperCase() }}</span>
                <span v-if="modalImage.v3_confidence" style="color:#666; margin-left:0.5rem">
                  ({{ (modalImage.v3_confidence * 100).toFixed(0) }}%)
                </span>
              </td>
            </tr>
            <tr v-if="modalImage.v3_label === 'keep' && modalImage.v3_use_yolo_crop !== null && modalImage.v3_use_yolo_crop !== undefined">
              <td>v3 crop choice</td>
              <td>
                <span v-if="modalImage.v3_use_yolo_crop" style="color:#22c55e">use YOLO crop ✓</span>
                <span v-else style="color:#0ea5e9; font-weight:600">use FULL image</span>
              </td>
            </tr>
            <tr v-if="modalImage.v3_reasoning">
              <td>v3 reasoning</td>
              <td><em>{{ modalImage.v3_reasoning }}</em></td>
            </tr>
            <tr v-if="v1V3Disagree(modalImage)">
              <td>v1 vs v3</td>
              <td>
                <span v-if="modalImage.v3_label === 'keep' && (modalImage.curation_status || '').endsWith('_drop')" style="color:#0ea5e9; font-weight:600">v3 RESCUED a v1 drop</span>
                <span v-else-if="modalImage.v3_label && modalImage.v3_label.startsWith('drop') && (modalImage.curation_status || '').endsWith('_keep')" style="color:#d97706; font-weight:600">v3 dropped a v1 keep ({{ modalImage.v3_label }})</span>
              </td>
            </tr>
            <tr v-if="hasClaudeAny(modalImage)">
              <td colspan="2" style="background:#fef3c7; padding:0.5rem; font-weight:700; color:#92400e">
                Claude Opus 4.7 (smoke test, same image at 3 effort levels)
              </td>
            </tr>
            <template v-for="effort in ['low','medium','high']" :key="effort">
              <tr v-if="modalImage[`claude_${effort}_label`]">
                <td>claude {{ effort }}</td>
                <td>
                  <span v-if="modalImage[`claude_${effort}_label`] === 'keep'" style="color:#15803d; font-weight:600">KEEP</span>
                  <span v-else style="color:#b91c1c; font-weight:600">{{ modalImage[`claude_${effort}_label`].toUpperCase() }}</span>
                  <span v-if="modalImage[`claude_${effort}_confidence`]" style="color:#666; margin-left:0.5rem">
                    ({{ (modalImage[`claude_${effort}_confidence`] * 100).toFixed(0) }}%)
                  </span>
                  <span v-if="modalImage[`claude_${effort}_label`] === 'keep' && modalImage[`claude_${effort}_use_yolo_crop`] !== undefined && modalImage[`claude_${effort}_use_yolo_crop`] !== null"
                        style="margin-left:0.5rem; font-size:0.85em">
                    <span v-if="modalImage[`claude_${effort}_use_yolo_crop`]" style="color:#22c55e">use YOLO crop</span>
                    <span v-else style="color:#0ea5e9">use FULL image</span>
                  </span>
                </td>
              </tr>
              <tr v-if="modalImage[`claude_${effort}_reason`]">
                <td>claude {{ effort }} reason</td>
                <td><em>{{ modalImage[`claude_${effort}_reason`] }}</em></td>
              </tr>
            </template>
            <tr v-if="hasClaudeAny(modalImage) && claudeEffortsDiffer(modalImage)">
              <td>claude effort split</td>
              <td style="color:#d97706; font-weight:600">
                Claude verdicts differ across effort levels — worth a closer look
              </td>
            </tr>
            <tr v-if="hasClaudeAny(modalImage) && claudeVsV1Disagrees(modalImage)">
              <td>claude vs v1</td>
              <td>
                <span style="color:#0ea5e9; font-weight:600">{{ claudeVsV1Disagrees(modalImage) }}</span>
              </td>
            </tr>
            <tr v-if="modalImage.gemini_pro_label">
              <td colspan="2" style="background:#ede9fe; padding:0.5rem; font-weight:700; color:#5b21b6">
                Gemini 3.1 Pro (Vertex Batch, 300-image diverse set)
              </td>
            </tr>
            <tr v-if="modalImage.gemini_pro_label">
              <td>gemini 3.1 pro</td>
              <td>
                <span v-if="modalImage.gemini_pro_label === 'keep'" style="color:#15803d; font-weight:600">KEEP</span>
                <span v-else style="color:#b91c1c; font-weight:600">{{ modalImage.gemini_pro_label.toUpperCase() }}</span>
                <span v-if="modalImage.gemini_pro_confidence" style="color:#666; margin-left:0.5rem">
                  ({{ (modalImage.gemini_pro_confidence * 100).toFixed(0) }}%)
                </span>
                <span v-if="modalImage.gemini_pro_label === 'keep' && modalImage.gemini_pro_use_yolo_crop !== undefined && modalImage.gemini_pro_use_yolo_crop !== null"
                      style="margin-left:0.5rem; font-size:0.85em">
                  <span v-if="modalImage.gemini_pro_use_yolo_crop" style="color:#22c55e">use YOLO crop</span>
                  <span v-else style="color:#0ea5e9">use FULL image</span>
                </span>
              </td>
            </tr>
            <tr v-if="modalImage.gemini_pro_reason">
              <td>gemini 3.1 pro reason</td>
              <td><em>{{ modalImage.gemini_pro_reason }}</em></td>
            </tr>
            <tr v-if="modalImage.gemini_pro_label && hasClaudeAny(modalImage) && (modalImage.gemini_pro_label !== (modalImage.claude_low_label || modalImage.claude_medium_label || modalImage.claude_high_label))">
              <td>claude vs gemini pro</td>
              <td style="color:#7c3aed; font-weight:600">
                disagree:
                Claude={{ (modalImage.claude_low_label || modalImage.claude_medium_label || modalImage.claude_high_label || '?').toUpperCase() }},
                Gemini Pro={{ modalImage.gemini_pro_label.toUpperCase() }}
              </td>
            </tr>
            <tr v-if="hasCodexAny(modalImage)">
              <td colspan="2" style="background:#dcfce7; padding:0.5rem; font-weight:700; color:#166534">
                OpenAI Codex (3 models × 2 efforts, same 45 images as Claude)
              </td>
            </tr>
            <template v-for="(combo, idx) in codexCombos" :key="idx">
              <tr v-if="modalImage[`codex_${combo.short}_${combo.effort}_label`]">
                <td>{{ combo.short }} {{ combo.effort }}</td>
                <td>
                  <span v-if="modalImage[`codex_${combo.short}_${combo.effort}_label`] === 'keep'" style="color:#15803d; font-weight:600">KEEP</span>
                  <span v-else style="color:#b91c1c; font-weight:600">{{ modalImage[`codex_${combo.short}_${combo.effort}_label`].toUpperCase() }}</span>
                  <span v-if="modalImage[`codex_${combo.short}_${combo.effort}_confidence`]" style="color:#666; margin-left:0.5rem">
                    ({{ (modalImage[`codex_${combo.short}_${combo.effort}_confidence`] * 100).toFixed(0) }}%)
                  </span>
                  <span v-if="modalImage[`codex_${combo.short}_${combo.effort}_label`] === 'keep' && modalImage[`codex_${combo.short}_${combo.effort}_use_yolo_crop`] !== undefined && modalImage[`codex_${combo.short}_${combo.effort}_use_yolo_crop`] !== null"
                        style="margin-left:0.5rem; font-size:0.85em">
                    <span v-if="modalImage[`codex_${combo.short}_${combo.effort}_use_yolo_crop`]" style="color:#22c55e">use YOLO crop</span>
                    <span v-else style="color:#0ea5e9">use FULL image</span>
                  </span>
                </td>
              </tr>
              <tr v-if="modalImage[`codex_${combo.short}_${combo.effort}_reason`]">
                <td>{{ combo.short }} {{ combo.effort }} reason</td>
                <td><em>{{ modalImage[`codex_${combo.short}_${combo.effort}_reason`] }}</em></td>
              </tr>
            </template>
            <tr v-if="hasCodexAny(modalImage) && hasClaudeAny(modalImage) && claudeVsCodexDisagree(modalImage)">
              <td>claude vs codex</td>
              <td style="color:#0ea5e9; font-weight:600">{{ claudeVsCodexDisagree(modalImage) }}</td>
            </tr>
            <tr v-if="modalImage.sam3_confidence !== null && modalImage.sam3_confidence !== undefined">
              <td>SAM3 insect conf</td>
              <td>{{ (modalImage.sam3_confidence * 100).toFixed(1) }}%
                  <span v-if="modalImage.sam3_kept">— kept for training</span>
                  <span v-else>— sent to OOD pool</span>
              </td>
            </tr>
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
const selectedSam3 = ref('')
const selectedYolo = ref('')
const selectedModel = ref('')
const selectedProVerdict = ref('')
const selectedV3 = ref('')
const selectedClaude = ref('')
const selectedCodex = ref('')
const selectedGeminiPro = ref('')
const searchText = ref('')
const viewMode = ref('grid')
const visibleCount = ref(100)
const modalImage = ref(null)
const modalImgNatural = ref(null)
const showBboxOverlay = ref(true)
const sortField = ref('')
const sortAsc = ref(true)

// SVG text size scales with image dimensions so labels stay readable on
// small thumbnails AND on full-res photos.
const bboxFontSize = computed(() => {
  if (!modalImgNatural.value) return 16
  return Math.max(modalImgNatural.value.w, modalImgNatural.value.h) * 0.025
})

function hasYoloBbox(img) {
  return Array.isArray(img.yolo_bbox) && img.yolo_bbox.length === 4
}

function hasYoloVerdict(img) {
  return img.yolo_confidence !== null && img.yolo_confidence !== undefined
}

function hasClaudeAny(img) {
  return !!(img.claude_low_label || img.claude_medium_label || img.claude_high_label)
}

const codexCombos = [
  { short: 'gpt54',      effort: 'low'    },
  { short: 'gpt54',      effort: 'medium' },
  { short: 'gpt54mini',  effort: 'low'    },
  { short: 'gpt54mini',  effort: 'medium' },
  { short: 'gpt53codex', effort: 'low'    },
  { short: 'gpt53codex', effort: 'medium' },
]

function hasCodexAny(img) {
  return codexCombos.some(c => img[`codex_${c.short}_${c.effort}_label`])
}

function codexLabels(img) {
  return codexCombos
    .map(c => img[`codex_${c.short}_${c.effort}_label`])
    .filter(Boolean)
}

function claudeMedianLabel(img) {
  return img.claude_medium_label || img.claude_low_label || img.claude_high_label
}

function claudeVsCodexDisagree(img) {
  // Compare Claude medium (or fall-through) vs gpt-5.4 medium (canonical Codex pick).
  const cl = claudeMedianLabel(img)
  const cx = img.codex_gpt54_medium_label || img.codex_gpt54_low_label
  if (!cl || !cx) return null
  const clKeep = cl === 'keep'
  const cxKeep = cx === 'keep'
  if (clKeep && !cxKeep) return `Codex (gpt-5.4) drops where Claude keeps (${cx})`
  if (!clKeep && cxKeep) return `Codex (gpt-5.4) keeps where Claude drops (${cl})`
  if (cl !== cx) return `Same direction, different reason: claude=${cl} codex=${cx}`
  return null
}

function codexEffortsDiffer(img) {
  // Across all 6 codex combos, do labels disagree?
  const labels = codexLabels(img)
  return labels.length >= 2 && labels.some(l => l !== labels[0])
}

function claudeEffortsDiffer(img) {
  const labels = ['claude_low_label', 'claude_medium_label', 'claude_high_label']
    .map(k => img[k])
    .filter(Boolean)
  if (labels.length < 2) return false
  const first = labels[0]
  return labels.some(l => l !== first)
}

function claudeVsV1Disagrees(img) {
  // Use medium as the canonical Claude verdict for the v1 comparison.
  const claudeLbl = img.claude_medium_label || img.claude_high_label || img.claude_low_label
  if (!claudeLbl) return null
  const v1 = img.curation_status || ''
  const v1Keep = v1.endsWith('_keep')
  const v1Drop = v1.endsWith('_drop')
  const cKeep = claudeLbl === 'keep'
  const cDrop = claudeLbl.startsWith('drop')
  if (v1Drop && cKeep) return `Claude RESCUED a v1 drop`
  if (v1Keep && cDrop) return `Claude dropped a v1 keep (${claudeLbl})`
  return null
}

function v1V3Disagree(img) {
  if (!img.v3_label) return false
  const v1Keep = (img.curation_status || '').endsWith('_keep')
  const v1Drop = (img.curation_status || '').endsWith('_drop')
  const v3Keep = img.v3_label === 'keep'
  const v3Drop = img.v3_label.startsWith('drop')
  return (v1Keep && v3Drop) || (v1Drop && v3Keep)
}

function onModalImgLoad(e) {
  modalImgNatural.value = {
    w: e.target.naturalWidth,
    h: e.target.naturalHeight,
  }
}

function closeModal() {
  modalImage.value = null
  modalImgNatural.value = null
}

onMounted(async () => {
  try {
    // Load summary first (tiny, instant)
    // Cache-bust both data files. Vite hashes JS/CSS but not /data/ assets,
    // so dataset additions otherwise serve stale from disk cache.
    const cacheBust = '?v=' + (window.__BUILD_TS__ || Date.now())
    const summaryRes = await fetch(import.meta.env.BASE_URL + 'data/dataset_summary.json' + cacheBust)
    summary.value = await summaryRes.json()

    // Stream dataset in chunks so UI renders progressively
    const dataRes = await fetch(import.meta.env.BASE_URL + 'data/dataset.json' + cacheBust)
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
  if (selectedSam3.value === 'kept') {
    imgs = imgs.filter(i => i.sam3_kept === true)
  } else if (selectedSam3.value === 'low') {
    imgs = imgs.filter(i => i.sam3_kept === false)
  } else if (selectedSam3.value === 'missing') {
    imgs = imgs.filter(i => i.sam3_confidence === null || i.sam3_confidence === undefined)
  }
  if (selectedYolo.value === 'kept') {
    imgs = imgs.filter(i => i.yolo_kept === true)
  } else if (selectedYolo.value === 'low') {
    imgs = imgs.filter(i => i.yolo_kept === false)
  } else if (selectedYolo.value === 'missing') {
    imgs = imgs.filter(i => i.yolo_confidence === null || i.yolo_confidence === undefined)
  }
  if (selectedModel.value === 'flash') {
    imgs = imgs.filter(i => i.pro_reviewed !== true && i.curation_status !== 'not_curated')
  } else if (selectedModel.value === 'pro_any') {
    imgs = imgs.filter(i => i.pro_reviewed === true)
  } else if (selectedModel.value === 'pro_rescued') {
    imgs = imgs.filter(i => i.pro_outcome === 'rescued')
  } else if (selectedModel.value === 'pro_confirmed_drop') {
    imgs = imgs.filter(i => i.pro_outcome === 'confirmed_drop')
  } else if (selectedModel.value === 'pro_relabeled') {
    imgs = imgs.filter(i => i.pro_outcome === 'relabeled_drop')
  }
  if (selectedProVerdict.value) {
    imgs = imgs.filter(i => i.pro_label === selectedProVerdict.value)
  }
  if (selectedV3.value) {
    const v = selectedV3.value
    if (v === 'keep') {
      imgs = imgs.filter(i => i.v3_label === 'keep')
    } else if (v === 'any_drop') {
      imgs = imgs.filter(i => i.v3_label && i.v3_label.startsWith('drop'))
    } else if (v.startsWith('drop_')) {
      imgs = imgs.filter(i => i.v3_label === v)
    } else if (v === 'rescue') {
      imgs = imgs.filter(i =>
        i.v3_label === 'keep' && (i.curation_status || '').endsWith('_drop')
      )
    } else if (v === 'v3_dropped_v1_keep') {
      imgs = imgs.filter(i =>
        i.v3_label && i.v3_label.startsWith('drop') &&
        (i.curation_status || '').endsWith('_keep')
      )
    } else if (v === 'v3_use_yolo_true') {
      imgs = imgs.filter(i => i.v3_label === 'keep' && i.v3_use_yolo_crop === true)
    } else if (v === 'v3_use_yolo_false') {
      imgs = imgs.filter(i => i.v3_label === 'keep' && i.v3_use_yolo_crop === false)
    }
  }
  if (selectedClaude.value) {
    const v = selectedClaude.value
    const has = (i) => !!(i.claude_low_label || i.claude_medium_label || i.claude_high_label)
    if (v === 'any') {
      imgs = imgs.filter(has)
    } else if (v === 'efforts_differ') {
      imgs = imgs.filter(i => {
        const labels = [i.claude_low_label, i.claude_medium_label, i.claude_high_label]
          .filter(Boolean)
        return labels.length >= 2 && labels.some(l => l !== labels[0])
      })
    } else if (v === 'claude_rescue') {
      imgs = imgs.filter(i => {
        const c = i.claude_medium_label || i.claude_high_label || i.claude_low_label
        return c === 'keep' && (i.curation_status || '').endsWith('_drop')
      })
    } else if (v === 'claude_dropped_v1_keep') {
      imgs = imgs.filter(i => {
        const c = i.claude_medium_label || i.claude_high_label || i.claude_low_label
        return c && c.startsWith('drop') && (i.curation_status || '').endsWith('_keep')
      })
    } else if (v === 'claude_drop_any') {
      imgs = imgs.filter(i => {
        const c = i.claude_medium_label
        return c && c.startsWith('drop')
      })
    } else if (v === 'claude_drop_other') {
      imgs = imgs.filter(i => {
        const labels = [i.claude_low_label, i.claude_medium_label, i.claude_high_label]
        return labels.some(l => l === 'drop_other')
      })
    } else if (v === 'claude_keep_all') {
      imgs = imgs.filter(i =>
        i.claude_low_label === 'keep' &&
        i.claude_medium_label === 'keep' &&
        i.claude_high_label === 'keep'
      )
    } else if (v === 'claude_use_yolo_true') {
      imgs = imgs.filter(i => {
        const efforts = ['low', 'medium', 'high']
        return efforts.some(e =>
          i[`claude_${e}_label`] === 'keep' && i[`claude_${e}_use_yolo_crop`] === true
        )
      })
    } else if (v === 'claude_use_yolo_false') {
      imgs = imgs.filter(i => {
        const efforts = ['low', 'medium', 'high']
        return efforts.some(e =>
          i[`claude_${e}_label`] === 'keep' && i[`claude_${e}_use_yolo_crop`] === false
        )
      })
    }
  }
  if (selectedCodex.value) {
    const v = selectedCodex.value
    const has = (i) => codexCombos.some(c => i[`codex_${c.short}_${c.effort}_label`])
    if (v === 'any') {
      imgs = imgs.filter(has)
    } else if (v === 'combos_differ') {
      imgs = imgs.filter(i => {
        const labels = codexCombos
          .map(c => i[`codex_${c.short}_${c.effort}_label`])
          .filter(Boolean)
        return labels.length >= 2 && labels.some(l => l !== labels[0])
      })
    } else if (v === 'claude_vs_codex') {
      imgs = imgs.filter(i => {
        const cl = i.claude_medium_label || i.claude_low_label || i.claude_high_label
        const cx = i.codex_gpt54_medium_label || i.codex_gpt54_low_label
        return cl && cx && cl !== cx
      })
    } else if (v === 'codex_drop_other') {
      imgs = imgs.filter(i =>
        codexCombos.some(c => i[`codex_${c.short}_${c.effort}_label`] === 'drop_other')
      )
    } else if (v === 'codex_keep_all') {
      imgs = imgs.filter(i => {
        const labels = codexCombos.map(c => i[`codex_${c.short}_${c.effort}_label`])
        return labels.every(l => l === 'keep')
      })
    }
  }
  if (selectedGeminiPro.value) {
    const v = selectedGeminiPro.value
    const cl = (i) => i.claude_medium_label || i.claude_low_label || i.claude_high_label
    if (v === 'any') {
      imgs = imgs.filter(i => i.gemini_pro_label)
    } else if (v === 'claude_vs_gp_disagree') {
      imgs = imgs.filter(i => i.gemini_pro_label && cl(i) && i.gemini_pro_label !== cl(i))
    } else if (v === 'gp_keep_claude_drop') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'keep' && cl(i) && cl(i) !== 'keep')
    } else if (v === 'gp_drop_claude_keep') {
      imgs = imgs.filter(i => i.gemini_pro_label && i.gemini_pro_label !== 'keep' && cl(i) === 'keep')
    } else if (v === 'gp_dead') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'drop_dead' || i.gemini_pro_label === 'dead')
    } else if (v === 'gp_multiple') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'drop_multiple' || i.gemini_pro_label === 'multiple')
    } else if (v === 'gp_quality') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'drop_quality' || i.gemini_pro_label === 'quality')
    } else if (v === 'gp_larva') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'drop_larva' || i.gemini_pro_label === 'larva')
    } else if (v === 'gp_other') {
      imgs = imgs.filter(i => i.gemini_pro_label === 'drop_other' || i.gemini_pro_label === 'other')
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

function proBadgeLabel(img) {
  if (img.pro_outcome === 'rescued') return 'PRO ✓'
  if (img.pro_outcome === 'confirmed_drop') return 'PRO ✗'
  if (img.pro_outcome === 'relabeled_drop') return 'PRO ↺'
  return 'PRO'
}

function proBadgeTitle(img) {
  if (img.pro_outcome === 'rescued') {
    return `Pro RESCUED — Flash had labeled "${img.flash_label_was}" but Pro relabeled to keep`
  }
  if (img.pro_outcome === 'confirmed_drop') {
    return `Pro confirmed Flash's drop label "${img.flash_label_was}"`
  }
  if (img.pro_outcome === 'relabeled_drop') {
    return `Pro changed drop reason: Flash said "${img.flash_label_was}" → Pro said "${img.pro_label}"`
  }
  return 'Reviewed by Gemini 3.1 Pro'
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

.pro-badge {
  position: absolute; top: 0.4rem; left: 0.4rem;
  padding: 0.15rem 0.45rem; border-radius: 3px;
  font-size: 0.65rem; font-weight: 700;
  background: #6f42c1; color: white;
  letter-spacing: 0.04em;
}
.pro-badge.rescued { background: #28a745; }     /* green = Pro saved it */
.pro-badge.confirmed { background: #6c757d; }   /* gray = Pro agreed it's a drop */
.pro-badge.relabeled { background: #d97706; }   /* orange = Pro changed reason */
.sam3-badge {
  position: absolute; bottom: 0.4rem; right: 0.4rem;
  padding: 0.15rem 0.45rem; border-radius: 3px;
  font-size: 0.65rem; font-weight: 700;
  background: #2e7be8; color: white;
}
.sam3-badge.low {
  background: #888;
  opacity: 0.85;
}
.yolo-badge {
  position: absolute; bottom: 0.4rem; left: 0.4rem;
  padding: 0.15rem 0.45rem; border-radius: 3px;
  font-size: 0.65rem; font-weight: 700;
  background: #16a34a; color: white;
}
.yolo-badge.low {
  background: #999;
  opacity: 0.85;
}

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
.modal-image-wrap { position: relative; background: #f5f5f5; line-height: 0; }
.modal-image-wrap > img { width: 100%; max-height: 60vh; object-fit: contain; display: block; }
.bbox-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.bbox-best { fill: none; stroke-width: 4; }
.bbox-best.bbox-kept { stroke: #22c55e; }
.bbox-best.bbox-dropped { stroke: #f59e0b; stroke-dasharray: 8 4; }
.bbox-other { fill: none; stroke: rgba(255, 255, 255, 0.7); stroke-width: 2; stroke-dasharray: 4 3; }
.bbox-label { font-weight: 700; paint-order: stroke; stroke: rgba(0,0,0,0.6); stroke-width: 3; stroke-linejoin: round; }
.bbox-label.bbox-kept { fill: #22c55e; }
.bbox-label.bbox-dropped { fill: #f59e0b; }
.bbox-toggle { position: absolute; top: 0.5rem; left: 0.5rem; display: flex; flex-direction: column; gap: 0.25rem; align-items: flex-start; line-height: 1.2; font-size: 0.8rem; }
.bbox-toggle label { background: rgba(0,0,0,0.6); color: white; padding: 0.25rem 0.5rem; border-radius: 4px; cursor: pointer; user-select: none; }
.bbox-toggle input { margin-right: 0.3rem; }
.bbox-flag { padding: 0.2rem 0.5rem; border-radius: 4px; color: white; font-weight: 600; font-size: 0.7rem; }
.bbox-flag-kept { background: #22c55e; }
.bbox-flag-low { background: #f59e0b; }
.bbox-flag-none { background: #ef4444; }
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
