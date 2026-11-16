<template>
  <ParkHome
    :spots="spots"
    :routes="routes"
    :catalog-error="error"
    :active="active"
    @planning="openPlanning"
    @catalog="openCatalog"
    @ai="$emit('ai')"
    @retry="load"
    @map-change="$emit('map-change', $event)"
  />
</template>
<script>
import ParkHome from '../../components/ParkHome.vue'
import { BASE_URL } from '../../common/config.js'

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
    return { spots: [], routes: [], error: '', loading: false, loaded: false }
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
    // 景点详情按钮先进入景点列表（Web 详情模块），列表里再打开单个景点详情
    openCatalog() { uni.navigateTo({ url: '/pages/scenic/scenic' }) },
    openPlanning(payload) {
      const spot = payload && payload.spot
      if (spot && spot.spot_id) {
        uni.navigateTo({ url: '/pages/scenic/scenic?spotId=' + spot.spot_id })
        return
      }
      const query = payload && payload.wander ? '?wander=1' : (payload && payload.featured ? '?featured=1' : '')
      uni.navigateTo({ url: '/pages/tour-guide/tour-guide' + query })
    },
  },
}
</script>
<style scoped>
:deep(.park-home) { height: 100%; }
</style>
