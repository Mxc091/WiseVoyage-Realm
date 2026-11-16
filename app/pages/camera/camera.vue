<template>
  <view class="cam-page">
    <view class="cam-head">
      <text class="cam-title">镜头导览</text>
      <view class="cam-close" @tap="close"><view class="cam-icon cam-icon-x"></view></view>
    </view>
    <view class="cam-preview" :class="{large:cameraLarge}" @tap="cameraLarge=!cameraLarge">
      <camera class="cam-view" :device-position="position" flash="off" mode="normal" @error="onCamError"></camera>
      <view v-if="cameraLarge" class="cam-shrink" @tap.stop="cameraLarge=false">缩小</view>
    </view>
    <view v-if="camError" class="cam-error">{{ camError }}</view>
    <view class="cam-status">
      <view class="cam-dots"><view v-for="i in 3" :key="i" class="cam-dot"></view></view>
      <text class="cam-hint">{{ listening ? '请说话…' : '镜头对准景点，我来讲解' }}</text>
      <view class="cam-line" v-if="myText"><text class="cam-line-tag">我</text><text class="cam-line-text">{{ myText }}</text></view>
      <view class="cam-line" v-if="aiReply"><text class="cam-line-tag">数字人</text><text class="cam-line-text">{{ aiReply }}</text></view>
    </view>
    <view class="cam-controls">
      <view class="cam-btn" :class="{on:listening}" @tap="toggleListen"><view class="cam-icon cam-icon-mic"></view></view>
      <view class="cam-btn" @tap="flip"><text class="cam-btn-text">翻转</text></view>
      <view class="cam-btn cam-btn-close" @tap="close"><view class="cam-icon cam-icon-x"></view></view>
    </view>
  </view>
</template>
<script>
import { BASE_URL } from '../../common/config.js'
export default {
  data: function () { return { position: 'back', listening: false, recording: false, myText: '', aiReply: '', camError: '', cameraLarge: false } },
  onLoad: function () {
    const self = this
    // #ifdef APP-PLUS
    try {
      plus.android.requestPermissions(['android.permission.CAMERA'], function (r) {
        if ((r.deniedAlways && r.deniedAlways.length) || (r.deniedPresent && r.deniedPresent.length)) self.camError = '相机权限未开启，请到系统设置开启'
      }, function () {})
    } catch (e) {}
    // #endif
    const recorder = uni.getRecorderManager()
    recorder.onStop(function (res) {
      self.recording = false; self.listening = false
      const path = res && res.tempFilePath
      if (!path) { uni.showToast({ title: '录音失败，请重试', icon: 'none' }); return }
      uni.showLoading({ title: '正在识别…' })
      uni.uploadFile({
        url: BASE_URL + '/tour-session/asr-upload', filePath: path, name: 'file', timeout: 60000,
        success: function (r) {
          uni.hideLoading()
          let d = {}
          try { d = JSON.parse(r.data) } catch (e) {}
          const text = typeof d.data === 'string' ? d.data : (d.data && d.data.text) || ''
          if (!text) { uni.showToast({ title: d.message || '没听清，请再说一次', icon: 'none' }); return }
          self.myText = text
          try { const ch = self.getOpenerEventChannel && self.getOpenerEventChannel(); if (ch && ch.emit) ch.emit('spoken', text) } catch (e) {}
        },
        fail: function () { uni.hideLoading(); uni.showToast({ title: '语音识别失败，请检查网络', icon: 'none' }) }
      })
    })
    recorder.onError(function () { self.recording = false; self.listening = false })
    this._recorder = recorder
    this._onReply = function (text) { self.aiReply = text || '' }
    uni.$on('camera-ai-reply', this._onReply)
  },
  onUnload: function () { if (this._onReply) uni.$off('camera-ai-reply', this._onReply) },
  methods: {
    close: function () { uni.navigateBack() },
    flip: function () { this.position = this.position === 'back' ? 'front' : 'back' },
    onCamError: function (e) { this.camError = '相机打开失败：' + ((e && e.detail && e.detail.errMsg) || '请检查权限') },
    toggleListen: function () {
      const self = this
      if (self.recording) { self._recorder && self._recorder.stop(); return }
      self.recording = true; self.listening = true
      const start = function () { self._recorder.start({ duration: 60000, sampleRate: 16000, numberOfChannels: 1, encodeBitRate: 48000, format: 'mp3' }) }
      // #ifdef APP-PLUS
      try {
        plus.android.requestPermissions(['android.permission.RECORD_AUDIO'], function (result) {
          if ((result.deniedAlways && result.deniedAlways.length) || (result.deniedPresent && result.deniedPresent.length)) { self.recording = false; self.listening = false; uni.showToast({ title: '需要麦克风权限', icon: 'none' }); return }
          start()
        }, function () { self.recording = false; self.listening = false })
      } catch (e) { self.recording = false; self.listening = false }
      // #endif
    }
  }
}
</script>
<style scoped>
.cam-page{position:fixed;top:0;right:0;bottom:0;left:0;display:flex;flex-direction:column;background:#0f0b16}
.cam-head{display:flex;align-items:center;justify-content:space-between;padding:calc(env(safe-area-inset-top) + 18rpx) 28rpx 18rpx}
.cam-title{font-size:28rpx;color:#fff;font-weight:600}
.cam-close{width:64rpx;height:64rpx;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.16)}
.cam-icon{width:36rpx;height:36rpx;background-color:#fff;-webkit-mask-size:contain;mask-size:contain;-webkit-mask-position:center;mask-position:center;-webkit-mask-repeat:no-repeat}
.cam-icon-x{-webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M6 6l12 12M18 6L6 18'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M6 6l12 12M18 6L6 18'/%3E%3C/svg%3E")}
.cam-icon-mic{-webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='9' y='3' width='6' height='11' rx='3'/%3E%3Cpath d='M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8'/%3E%3C/svg%3E");mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='9' y='3' width='6' height='11' rx='3'/%3E%3Cpath d='M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8'/%3E%3C/svg%3E")}
.cam-preview{position:absolute;top:calc(env(safe-area-inset-top) + 96rpx);right:24rpx;width:240rpx;height:320rpx;background:#000;z-index:3;transition:all 220ms cubic-bezier(.2,.8,.2,1)}
.cam-view{display:block;width:240rpx;height:320rpx;background:#000}
.cam-preview.large{position:fixed;top:0;right:0;bottom:0;left:0;width:auto;height:auto;z-index:50}
.cam-preview.large .cam-view{width:100%;height:100%}
.cam-shrink{position:absolute;right:24rpx;top:calc(env(safe-area-inset-top) + 20rpx);padding:10rpx 24rpx;border-radius:999rpx;background:rgba(0,0,0,.55);color:#fff;font-size:24rpx;z-index:51}
.cam-error{padding:12rpx 28rpx;font-size:22rpx;color:#ffb4b4}
.cam-status{position:absolute;left:40rpx;right:300rpx;top:32%;display:flex;flex-direction:column;align-items:flex-start;gap:9rpx;z-index:2}
.cam-dots{display:flex;gap:10rpx;margin-bottom:8rpx}
.cam-dot{width:12rpx;height:12rpx;border-radius:50%;background:rgba(255,255,255,.6);animation:cd 1.2s infinite}
.cam-dot:nth-child(2){animation-delay:.2s}.cam-dot:nth-child(3){animation-delay:.4s}
@keyframes cd{0%,100%{opacity:.35}50%{opacity:1}}
.cam-hint{font-size:26rpx;color:rgba(255,255,255,.8)}
.cam-line{display:flex;gap:12rpx;margin-top:10rpx;width:100%}
.cam-line-tag{flex:none;font-size:22rpx;color:#b9a8ff}
.cam-line-text{flex:1;font-size:28rpx;line-height:1.6;color:#fff}
.cam-controls{display:flex;align-items:center;justify-content:center;gap:48rpx;padding:24rpx 0 calc(env(safe-area-inset-bottom) + 36rpx)}
.cam-btn{width:112rpx;height:112rpx;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.14);border:1rpx solid rgba(255,255,255,.25)}
.cam-btn.on{background:rgba(139,120,230,.5);border-color:#b9a8ff}
.cam-btn-close{background:rgba(224,90,90,.9);border-color:transparent}
.cam-btn-close .cam-icon{background-color:#fff}
.cam-btn-text{font-size:24rpx;color:#fff}
</style>
