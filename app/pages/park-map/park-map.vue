<template>
  <view class="guide-page" :class="{ 'guide-notice-page': notices }">
    <view class="guide-header">
      <button class="guide-back" :aria-label="t('返回')" @tap="back"><WanderIcon name="back" /></button>
      <text role="heading">{{ t(notices ? '官方通知' : '景区导览地图') }}</text>
    </view>

    <template v-if="notices">
      <view class="guide-notices">
        <button v-for="item in officialNotices" :key="item.title" class="guide-notice" @tap="openSource(item.url)">
          <DashboardIcon :name="item.icon" />
          <view><text>{{ t(item.title) }}</text><text class="guide-notice-detail">{{ t(item.detail) }}</text></view>
          <WanderIcon name="next" />
        </button>
      </view>
    </template>
    <template v-else>
      <movable-area class="guide-stage" :scale-area="true">
        <movable-view :key="resetVersion" direction="all" :scale="true"
          :scale-min="1" :scale-max="4" :scale-value="zoomCommand" :animation="false" @scale="onScale" class="guide-pan">
          <image class="guide-image" :src="mapImage" mode="aspectFit"
            :aria-label="t('颐和园官方导览地图')" @load="loaded = true" @error="imageFailed" />
        </movable-view>
      </movable-area>
      <view class="guide-footer">
        <text v-if="failed" class="guide-error">{{ t('导览图加载失败，请打开颐和园官网') }}</text>
        <view class="guide-tools">
          <button :disabled="!loaded || zoom <= 1" :aria-label="t('缩小地图')" @tap="changeZoom(-.5)"><WanderIcon name="minus" /></button>
          <button :disabled="!loaded" @tap="reset">{{ t('适应屏幕') }}</button>
          <button :disabled="!loaded || zoom >= 4" :aria-label="t('放大地图')" @tap="changeZoom(.5)"><WanderIcon name="plus" /></button>
        </view>
        <text class="guide-source">{{ t('来源：颐和园官网') }}</text>
      </view>
    </template>
  </view>
</template>

<script>
import WanderIcon from '../../components/WanderIcon.vue'
import DashboardIcon from '../../components/DashboardIcon.vue'

const site = 'https://www.summerpalace.net.cn'
const officialImage = site + '/Public/static/themes/image/pinning_img1.jpg'
const officialNotices = [
  { title: '景区公告', detail: '查看颐和园官网发布的最新通知', icon: 'bell', url: site + '/home.html' },
  { title: '游览提示及开放时间', detail: '查看开放时间、票务和游船信息', icon: 'clock', url: site + '/visit.html' },
]

export default {
  components: { WanderIcon, DashboardIcon },
  data() {
    return {
      officialNotices, notices: false,
      mapImage: '/static/park-dashboard/official-guide.webp',
      loaded: false, failed: false, zoom: 1, zoomCommand: 1, resetVersion: 0,
    }
  },
  onLoad(query) { this.notices = query?.view === 'notices' },
  methods: {
    back() { uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/tabs/tabs' }) }) },
    onScale(event) {
      const value = Number(event.detail?.scale)
      if (Number.isFinite(value)) this.zoom = value
    },
    changeZoom(amount) {
      const target = Math.max(1, Math.min(4, this.zoom + amount))
      // A pinch moves the live value independently of the last button command.
      if (target === this.zoomCommand) this.zoomCommand = this.zoom
      this.$nextTick(() => { this.zoomCommand = target })
    },
    reset() { this.zoom = this.zoomCommand = 1; this.resetVersion++ },
    imageFailed() {
      if (this.mapImage !== officialImage) this.mapImage = officialImage
      else this.failed = true
    },
    openSource(url) {
      // #ifdef H5
      window.open(url, '_blank', 'noopener,noreferrer')
      // #endif
      // #ifdef APP-PLUS
      plus.runtime.openURL(url)
      // #endif
    },
  },
}
</script>

<style scoped>
.guide-page {
  display: flex; flex-direction: column; width: 100%; height: 100vh; height: 100dvh;
  box-sizing: border-box; padding: var(--status-bar-height, 0px) 0 env(safe-area-inset-bottom);
  background: #f7f4ff; color: #302451;
}
.guide-header { height: 62px; display: flex; align-items: center; padding: 0 14px; gap: 12px; flex: none; font-size: 19px; }
.guide-header, .guide-footer { position: relative; z-index: 1; background: #f7f4ff; }
.guide-page:not(.guide-notice-page) .guide-header::after, .guide-footer::before {
  content: ''; position: absolute; left: 0; right: 0; height: 16px; pointer-events: none;
}
.guide-page:not(.guide-notice-page) .guide-header::after {
  top: 100%; background: linear-gradient(to bottom, #f7f4ff, #fff0);
}
.guide-footer::before { bottom: 100%; background: linear-gradient(to top, #f7f4ff, #fff0); }
.guide-page button { margin: 0; border: 0; padding: 0; color: inherit; line-height: inherit; font: inherit; }
.guide-page button::after { border: 0; }
.guide-page :is(.guide-back,.guide-tools button) {
  display: grid; place-items: center; min-height: 44px; min-width: 44px;
  border-radius: 14px; background: #ede6fb; color: #58428a;
}
.guide-stage { flex: 1; width: 100%; height: auto; min-height: 0; overflow: hidden; background: #fff; }
.guide-stage, .guide-pan { touch-action: none; }
.guide-pan, .guide-image { width: 100%; height: 100%; }
.guide-image { pointer-events: none; }
.guide-footer { flex: none; display: grid; justify-items: center; padding: 10px 16px 5px; }
.guide-tools { display: flex; gap: 8px; }
.guide-tools button:nth-child(2) { padding: 0 14px; font-size: 13px; }
.guide-tools button[disabled] { opacity: .5; }
.guide-source { font-size: 12px; padding: 10px 14px; color: #6b6278; white-space: nowrap; }
.guide-error { font-size: 13px; margin-bottom: 8px; }
.guide-notices { display: grid; gap: 12px; padding: 10px 16px; }
.guide-page .guide-notice {
  display: grid; grid-template-columns: 24px 1fr 22px; align-items: center; gap: 12px; text-align: left;
  min-height: 76px; border-radius: 16px; background: #fff; padding: 10px 14px;
}
.guide-notice-detail { display: block; font-size: 12px; color: #685b77; margin-top: 4px; }
</style>
