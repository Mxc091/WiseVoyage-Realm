<template>
  <view class="tabs-shell">
    <swiper class="pager-viewport" :current="pagerCurrent" :duration="260" :circular="false" :disable-touch="dockHidden || guest || (current === 0 && !planning)" :skip-hidden-item-layout="false" @change="onPagerChange" @animationfinish="onPagerFinish">
      <swiper-item>
        <view class="panel-slot">
          <ParkHome v-if="!planning" ref="home" :active="shellVisible && current === 0" :spots="catalog.spots" :routes="catalog.routes"
            :catalog-error="catalog.error" :selected-route-id="mapSelectedRouteId" @planning="openPlanning" @ai="openHomeAI"
            @retry="$refs.tour.loadData()" @map-change="parkMapOpen=$event" />
          <view v-show="planning" class="panel-slot">
            <TourGuide ref="tour" embedded-home @home="showHome" @catalog="catalog=$event" @theme-selected="mapSelectedRouteId=$event" />
          </view>
        </view>
      </swiper-item>
      <swiper-item><view class="panel-slot"><AiChat ref="ai" /></view></swiper-item>
      <swiper-item><view class="panel-slot"><Mine ref="mine" /></view></swiper-item>
    </swiper>
    <TabDock :current="pagerCurrent" :progress="pagerCurrent" :hidden="dockHidden" :ai-hidden="aiHidden" @select="onDockPick" />
  </view>
</template>
<script>
import TourGuide from '../tour-guide/tour-guide.vue'
import AiChat from '../ai-chat/ai-chat.vue'
import Mine from '../mine/mine.vue'
import TabDock from '../../components/TabDock.vue'
import ParkHome from '../../components/ParkHome.vue'
import { LOGIN_PROVIDER } from '../../common/config.js'
import { hasAppSession } from '../../common/onboarding.js'

const validIndex = index => Number.isInteger(index) && index >= 0 && index < 3
export default {
  components: { TourGuide, AiChat, Mine, TabDock, ParkHome },
  data() {
    return { current: 0, pagerCurrent: 0, pendingTab: null, switching: false,
      panelReady: false, shellVisible: false, shownPanel: null, initialized: [false, false, false],
      keyboardOpen: false, itineraryOpen: false, guest: false, planning: false, parkMapOpen: false, mapSelectedRouteId: null,
      catalog: { spots: [], routes: [], error: '' } }
  },
  computed: {
    dockHidden() { return this.keyboardOpen || this.itineraryOpen },
    aiHidden() { return this.pagerCurrent === 1 },
  },
  onLoad(query) {
    const index = ['tour', 'ai', 'mine'].indexOf((query && query.tab) || 'tour')
    this.guest = !hasAppSession(LOGIN_PROVIDER)
    this.current = this.pagerCurrent = this.guest || index < 0 ? 0 : index
    this._onKeyboard = event => { this.keyboardOpen = !!(event && event.height > 0) }
    if (uni.onKeyboardHeightChange) uni.onKeyboardHeightChange(this._onKeyboard)
    this._onDockSync = payload => { if (payload && payload.source === 'tour') this.itineraryOpen = !!payload.hide }
    this._onTabsSelect = payload => {
      const key = typeof payload === 'string' ? payload : (payload && payload.tab) || 'tour'
      if (key === 'tour' && (uni.getStorageSync('ai_spot_ids') || uni.getStorageSync('ai_route_plan'))) {
        this.openPlanning({})
      }
      this.selectTab(['tour', 'ai', 'mine'].indexOf(key))
    }
    uni.$on('dock:sync', this._onDockSync)
    uni.$on('tabs:select', this._onTabsSelect)
  },
  mounted() {
    this.$nextTick(() => {
      this.panelReady = true
      this.preparePanel(this.current)
      this.showPanel()
    })
  },
  onShow() { this.shellVisible = true; if (this.panelReady) this.showPanel() },
  onHide() {
    this.shellVisible = false
    this.hidePanel()
    this.pendingTab = null
    this.current = this.pagerCurrent
    this.switching = false
  },
  onUnload() {
    this.shellVisible = false
    this.hidePanel()
    for (let i = 0; i < 3; i++) if (this.initialized[i]) this.callHook(i, 'onUnload')
    if (uni.offKeyboardHeightChange && this._onKeyboard) uni.offKeyboardHeightChange(this._onKeyboard)
    uni.$off('dock:sync', this._onDockSync)
    uni.$off('tabs:select', this._onTabsSelect)
  },
  onBackPress() {
    const handled = this.callHook(this.current, 'onBackPress')
    if (handled || this.current !== 0) return handled
    if (this.planning) { this.showHome(); return true }
    if (this.parkMapOpen) { this.$refs.home?.backMap(); return true }
  },
  methods: {
    showHome() {
      this.planning = false
      this.itineraryOpen = false
    },
    openPlanning({ route, spot, wander, featured } = {}) {
      this.parkMapOpen = false
      this.planning = true
      this.$nextTick(() => {
        const planner = this.$refs.tour
        if (!planner) return
        if (wander) { planner.openWander(route, featured); return }
        if (route || spot) planner.switchPlanningTab('route')
        if (route) planner.openRoute(route)
        if (spot) planner.openDetail(spot)
      })
    },
    onDockPick(index) {
      if (index === 0) {
        if (this.planning) this.showHome()
        else if (this.current === 0 && this.parkMapOpen) this.$refs.home?.closeMap()
      }
      this.selectTab(index)
    },
    openHomeAI(context) {
      if (!this.guest) this._homeAIContext = context
      this.selectTab(1)
    },
    panel(index) { return [this.$refs.tour, this.$refs.ai, this.$refs.mine][index] || null },
    // Embedded pages retain their component instances; forward page hooks only when visible.
    hookFns(raw, output) {
      if (!raw) return output
      if (typeof raw === 'function') { output.push(raw); return output }
      if (Array.isArray(raw)) { raw.forEach(item => this.hookFns(item, output)); return output }
      if (typeof raw === 'object') { Object.values(raw).forEach(item => this.hookFns(item, output)) }
      return output
    },
    callHook(index, hook, arg) {
      const vm = this.panel(index)
      if (!vm || !vm.$options) return undefined
      const fns = this.hookFns(vm.$options[hook], [])
      let result
      for (const fn of fns) {
        try {
          const value = fn.call(vm, arg)
          if (value !== undefined) result = value
        } catch (error) { console.error('[tabs] ' + hook + ' failed', error) }
      }
      return result
    },
    preparePanel(index) {
      if (this.initialized[index] || !this.panelReady) return
      this.initialized[index] = true
      this.callHook(index, 'onLoad', {})
      this.callHook(index, 'onReady')
    },
    hidePanel() {
      if (this.shownPanel == null) return
      this.callHook(this.shownPanel, 'onHide')
      this.shownPanel = null
    },
    showPanel() {
      if (!this.shellVisible || !this.panelReady || this.shownPanel === this.current) return
      this.hidePanel()
      this.preparePanel(this.current)
      this.shownPanel = this.current
      this.callHook(this.current, 'onShow')
      if (this.current === 1 && this._homeAIContext) {
        const context = this._homeAIContext
        this._homeAIContext = null
        this.$nextTick(() => this.$refs.ai?.openFromPark(context))
      }
    },
    selectTab(index) {
      if (!validIndex(index)) return
      if (index !== 0 && this.guest) {
        uni.navigateTo({ url: '/pages/auth/auth' })
        return
      }
      if (this.switching) { this.pendingTab = index === this.pagerCurrent ? null : index; return }
      if (index === this.current) return
      this.preparePanel(index)
      this.switching = true
      this.pagerCurrent = index
      if (uni.hideKeyboard) uni.hideKeyboard()
    },
    onPagerChange(event) {
      const index = event && event.detail && event.detail.current
      if (!validIndex(index)) return
      this.preparePanel(index)
      this.pagerCurrent = index
      this.switching = index !== this.current
    },
    onPagerFinish(event) {
      const index = event && event.detail && event.detail.current
      if (!validIndex(index) || index !== this.pagerCurrent) return
      this.current = index
      this.switching = false
      this.showPanel()
      const next = this.pendingTab
      this.pendingTab = null
      if (next != null && next !== index) this.$nextTick(() => this.selectTab(next))
    },
  },
}
</script>
<style scoped>
.tabs-shell{width:100%;height:100vh;height:100dvh;overflow:hidden;background:linear-gradient(135deg,#eee8ff 0%,#fbfbff 52%,#eef8fc 100%)}
.pager-viewport{width:100%;height:100%;overflow:hidden}
.pager-viewport :deep(.uni-swiper-wrapper){overflow:clip}
.panel-slot{width:100%;height:100%;overflow:hidden;contain:layout}
</style>
<style>
/* Keep the shared background still while the cached pages move above it. */
.panel-slot .aurora-background{display:none}
</style>
