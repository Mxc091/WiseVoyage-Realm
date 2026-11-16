<template>
  <ParkHome
    :spots="spots"
    :routes="routes"
    :catalog-error="error"
    :active="active"
    @planning="openPlanning"
    @catalog="openCatalog"
    @claim-scan="scanRoute"
    @ai="$emit('ai', $event)"
    @retry="load"
    @map-change="$emit('map-change', $event)"
  />
</template>
<script>
import ParkHome from '../../components/ParkHome.vue'
import { BASE_URL, isLocalStationOrigin } from '../../common/config.js'
import { CLAIM_ROUTE, saveClaim } from '../../common/station-claim.js'
import { sharedPlanUrl } from '../../common/wander-handoff.js'

function req(path) {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token') || ''
    uni.request({
      url: BASE_URL + path,
      timeout: 8500,
      method: 'GET',
      header: Object.assign({ 'Content-Type': 'application/json' }, token ? { Authorization: 'Bearer ' + token } : {}),
      success: response => response.statusCode === 200 ? resolve(response.data) : reject(new Error('数据暂不可用')),
      fail: reject,
    })
  })
}

export default {
  components: { ParkHome },
  props: { active: { type: Boolean, default: true } },
  emits: ['ai', 'map-change'],
  data() {
    return { spots: [], routes: [], error: '', loading: false, loaded: false, scanning: false }
  },
  created() { this.load() },
  methods: {
    async load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        const [spotsData, routesData] = await Promise.all([req('/tour-session/spots'), req('/tour-session/routes')])
        const spots = spotsData && spotsData.data ? spotsData.data : {}
        const routes = routesData && routesData.data ? routesData.data : {}
        this.spots = spots.spot_list || spots.spots || []
        this.routes = routes.route_list || routes.routes || []
        this.loaded = true
      } catch (error) {
        this.error = '数据暂不可用，请检查网络后重试'
      } finally {
        this.loading = false
      }
    },
    refresh() { if (!this.loaded) this.load() },
    // 扫码领取路线：扫描电脑网页上的路线二维码，打开路线确认页
    scanRoute() {
      if (this.scanning) return
      this.scanning = true
      uni.scanCode({ onlyFromCamera: false, scanType: ['qrCode'],
        success: result => {
          let claim
          try { claim = saveClaim(result && result.result) }
          catch (_) { uni.showToast({ title: '请扫描网页上的路线领取码', icon: 'none' }); return }
          if (claim.origin && !isLocalStationOrigin(claim.origin)) { uni.showToast({ title: '只允许连接局域网电脑的18000端口', icon: 'none' }); return }
          const query = 'claim=' + encodeURIComponent(claim.token || '') + '&server=' + encodeURIComponent(claim.origin || '')
          uni.navigateTo({ url: CLAIM_ROUTE + '?' + query, fail: () => uni.showToast({ title: '打开领取页失败，请重试', icon: 'none' }) })
        },
        fail: err => { if (!String(err && err.errMsg || '').includes('cancel')) uni.showToast({ title: '扫码失败，请检查相机权限', icon: 'none' }) },
        complete: () => { this.scanning = false }
      })
    },
    // 景点详情按钮先进入景点列表（Web 详情模块），列表里再打开单个景点详情
    openCatalog() { uni.navigateTo({ url: '/pages/scenic/scenic' }) },
    openPlanning(payload) {
      const spot = payload && payload.spot
      if (spot && spot.spot_id) {
        uni.navigateTo({ url: '/pages/scenic/scenic?spotId=' + spot.spot_id })
        return
      }
      // 「路线规划」：优先回到最近一次存入的随心逛路线，没有才打开空白规划
      if (!payload || (!payload.wander && !payload.featured && !payload.route)) {
        let last = null
        try { last = uni.getStorageSync('wander-last-handoff') } catch (_) {}
        if (last && Array.isArray(last.ids) && last.ids.length) {
          try { uni.navigateTo({ url: sharedPlanUrl(last) }); return } catch (_) {}
        }
      }
      // 随心逛有自己的规划页（WanderPlanner），不进智能导览
      if (payload && payload.wander && !payload.featured && !payload.route) {
        uni.navigateTo({ url: '/pages/tour-guide/tour-guide?wander=1' })
        return
      }
      // 主题路线卡片仍打开网页版的规划视图
      const route = payload && payload.route
      const spotIds = route && Array.isArray(route.spot_ids) && route.spot_ids.length ? route.spot_ids.join(',') : ''
      uni.navigateTo({ url: '/pages/scenic/scenic?view=plan' + (spotIds ? '&spotIds=' + spotIds : '') })
    },
  },
}
</script>
<style scoped>
:deep(.park-home) { height: 100%; }
</style>
