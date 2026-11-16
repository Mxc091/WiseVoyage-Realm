<template>
  <view class="scenic-shell">
    <web-view :src="src" @message="onMessage"></web-view>
  </view>
</template>

<script>
import { scenicWebOrigin } from '../../common/config.js'

export default {
  data() {
    return { src: '', deviceId: '' }
  },
  onLoad(query) {
    const spotId = query && query.spotId ? String(query.spotId) : ''
    let device = ''
    try { device = uni.getStorageSync('device_id') || '' } catch (e) {}
    if (!device) {
      device = 'dev-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
      try { uni.setStorageSync('device_id', device) } catch (e) {}
    }
    this.deviceId = device
    this.src = scenicWebOrigin() + '/app/scenic' + (spotId ? '/' + spotId : '') + '?device=' + encodeURIComponent(device)

    // #ifdef APP-PLUS
    const apply = () => {
      try {
        const window = plus.android.runtimeMainActivity().getWindow()
        const Color = plus.android.importClass('android.graphics.Color')
        window.setNavigationBarColor(Color.parseColor('#0d0a16'))
        plus.navigator.setStatusBarStyle('dark')
        plus.navigator.setStatusBarBackground('#ffffff')
      } catch (error) {}
    }
    if (typeof plus !== 'undefined') apply()
    else document.addEventListener('plusready', apply, { once: true })
    // #endif
  },
  onReady() {
    // Pass authentication inside the native WebView instead of putting it in a URL.
    // #ifdef APP-PLUS
    const page=this.$scope.$getAppWebview()
    const attach=()=>page.children().forEach(view=>{
      const inject=()=>{
        const token=String(uni.getStorageSync('token')||'')
        view.evalJS('try{window.sessionStorage.setItem("scenic-app-token",'+JSON.stringify(token)+')}catch(e){}')
      }
      if(!view.__scenicAuthBound){view.__scenicAuthBound=true;view.addEventListener('loaded',inject)}
      inject()
    })
    attach()
    setTimeout(attach,300)
    // #endif
  },
  onShow() {
    try {
      if (typeof plus !== 'undefined' && plus.navigator) plus.navigator.setFullscreen(false)
    } catch (error) {}
  },
  methods: {
    onMessage(event) {
      const messages = event && event.detail && event.detail.data
      const last = Array.isArray(messages) ? messages[messages.length - 1] : messages
      if (last && last.type === 'scenic-back') uni.navigateBack()
      if (last && last.type === 'save-checkin' && last.spot) {
        const list = uni.getStorageSync('my_checkins') || []
        list.unshift({ id: Date.now(), spot_name: last.spot, time: new Date(last.time || Date.now()).toLocaleString() })
        uni.setStorageSync('my_checkins', list.slice(0, 50))
      }
      if (last && last.type === 'open-tour-page' && last.sessionId) {
        uni.navigateTo({ url: '/pages/tour/tour?sessionId=' + last.sessionId })
      }
    }
  }
}
</script>

<style>
page { background: #ffffff !important; }
.scenic-shell { position: relative; width: 100%; height: 100vh; background: #ffffff; }
</style>
