<script setup lang="ts">
import { computed } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'
import type { StationSpot } from '@/api/serviceStation'
import { locale, t } from '@/i18n'
import ScenicSpotCover from './ScenicSpotCover.vue'

const props = defineProps<{ spots: StationSpot[] }>()
defineEmits<{ select: [spot: StationSpot] }>()
const reducedMotion = usePreferredReducedMotion()
const flowing = computed(() => props.spots.length >= 8 && reducedMotion.value !== 'reduce')
const rows = computed(() => {
  if (!flowing.value) return [props.spots]
  const half = Math.ceil(props.spots.length / 2)
  return [props.spots.slice(0, half), props.spots.slice(half)]
})
</script>
<template>
  <section class="scenic-wall" :class="{ flowing }" :aria-label="locale === 'en' ? 'Attractions' : '景点'">
    <div v-for="(row, lane) in rows" :key="lane" class="wall-lane">
      <div class="wall-track" :style="{ '--period': row.length * 9 + 's' }">
        <div v-for="copy in (flowing ? 2 : 1)" :key="copy" class="wall-group" :aria-hidden="copy === 2 || undefined">
          <button v-for="spot in row" :key="spot.spot_id" type="button" class="wall-tile"
            :tabindex="copy === 2 ? -1 : 0" @click="$emit('select', spot)">
            <ScenicSpotCover :spot="spot" class="wall-photo" aria-hidden="true" />
            <span class="wall-name">{{ t(spot.spot_name) }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
<style scoped>
.scenic-wall { container-type:inline-size; --gap:12px; --tile:clamp(144px, 23cqw, 320px); }
.wall-lane { overflow:hidden; border-radius:16px; }
.wall-lane + .wall-lane { margin-top:var(--gap); }
.wall-group { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,var(--tile)),1fr)); gap:var(--gap); }
.scenic-wall .wall-tile { position:relative; padding:0; border:0; overflow:hidden; border-radius:14px; aspect-ratio:1.35; background:#23382f; text-align:start; color:white; }
.wall-photo { position:absolute; inset:0; width:100%; height:100%; }
.wall-name { position:absolute; inset:auto 0 0; padding:36px 14px 12px; font-size:clamp(18px,2cqw,24px); font-weight:600; line-height:1.3; background:linear-gradient(transparent,rgba(12,23,27,.85)); }
.flowing .wall-track { display:flex; width:max-content; animation:wall-drift var(--period) linear infinite; }
.flowing .wall-group { display:flex; padding-right:var(--gap); }
.flowing .wall-tile { width:var(--tile); flex:none; }
.flowing .wall-lane:last-child .wall-track { animation-direction:reverse; }
.wall-lane:focus-within .wall-track { animation-play-state:paused; }
@media(hover:hover) { .wall-lane:hover .wall-track { animation-play-state:paused; } }
.flowing .wall-lane:has(:focus-visible) { overflow-x:auto; }
.flowing .wall-lane:has(:focus-visible) .wall-track { animation:none; }
.flowing .wall-lane:has(:focus-visible) .wall-group[aria-hidden] { display:none; }
.scenic-wall .wall-tile:focus-visible { outline-offset:-4px; }
@keyframes wall-drift { to { transform:translateX(-50%); } }
</style>
