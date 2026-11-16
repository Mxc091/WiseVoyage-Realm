<template>
  <view
    class="welcome"
    @touchstart="startSwipe" @touchmove="moveSwipe"
    @touchend="endSwipe" @touchcancel="resetSwipe"
  >
    <view class="welcome-photo" aria-hidden="true" />
    <view class="welcome-shade" :class="{ 'is-leaving': leaving }" aria-hidden="true" />
    <view class="welcome-content" :class="{ 'is-dragging': dragging, 'is-leaving': leaving }" :style="motionStyle"
      @transitionend="finishTransition"
    >
      <view class="welcome-type" role="heading" :aria-label="english ? 'Hi! Summer Palace welcomes you.' : 'Hi! 欢迎来到颐和园'">
        <image class="welcome-hi" src="/static/welcome-summer-palace/hi.svg" mode="scaleToFill" aria-hidden="true" />
        <view class="welcome-line" aria-hidden="true">
          <image class="welcome-word" src="/static/welcome-summer-palace/welcomes.svg" mode="scaleToFill" />
          <text class="welcome-destination" :class="{ 'is-english': english }">{{ english ? 'Summer Palace' : '颐和园' }}</text>
        </view>
      </view>
      <button class="welcome-enter" hover-class="none" :disabled="leaving"
        :aria-label="english ? 'Swipe up or tap to enter' : '上滑或点击进入首页'" @tap="beginEntry"
      >
        <view class="welcome-arrow" aria-hidden="true">
          <image class="welcome-chevron" src="/static/welcome-summer-palace/chevrons.svg" mode="scaleToFill" />
        </view>
      </button>
    </view>
  </view>
</template>

<script>
import { LANGUAGE_STORAGE_KEY } from '../../common/tour-language.js'
import { HOME_URL, ONBOARDING_STORAGE_KEY } from '../../common/onboarding.js'
import { CLAIM_ROUTE, pendingClaim } from '../../common/station-claim.js'

const SWIPE_DISTANCE = 56
const EXIT_DURATION = 460

// #ifdef H5
// uni-view normalizes template events and does not retain native mouse pointer fields.
const MOUSE_EVENTS = {
  pointerdown: 'startMouseSwipe',
  pointermove: 'moveMouseSwipe',
  pointerup: 'endMouseSwipe',
  pointercancel: 'cancelMouseSwipe',
  pointerleave: 'cancelMouseSwipe',
}
// #endif

export default {
  data() {
    return { english: false, dragging: false, leaving: false, offset: 0 }
  },
  computed: {
    motionStyle() { return { '--swipe-offset': this.offset + 'px', '--exit-duration': EXIT_DURATION + 'ms' } },
  },
  onLoad() {
    this.english = uni.getStorageSync(LANGUAGE_STORAGE_KEY) === 'en'
    if (uni.getStorageSync(ONBOARDING_STORAGE_KEY)) {
      this.leaving = true
      this.openEntry()
    }
  },
  onUnload() { clearTimeout(this._exitTimer) },
  // #ifdef H5
  mounted() {
    for (const [type, handler] of Object.entries(MOUSE_EVENTS)) this.$el.addEventListener(type, this[handler])
  },
  beforeUnmount() {
    for (const [type, handler] of Object.entries(MOUSE_EVENTS)) this.$el.removeEventListener(type, this[handler])
  },
  // #endif
  methods: {
    // #ifdef H5
    mouseTouch(event) {
      return { identifier: event.pointerId, clientX: event.clientX, clientY: event.clientY }
    },
    startMouseSwipe(event) {
      if (event.pointerType === 'mouse' && event.button === 0) this.startSwipe({ touches: [this.mouseTouch(event)] })
    },
    moveMouseSwipe(event) {
      if (event.pointerType !== 'mouse' || !this._gesture) return
      if (event.buttons !== 1) { this.resetSwipe(); return }
      this.moveSwipe({ touches: [this.mouseTouch(event)] })
      if (this.dragging && event.currentTarget?.setPointerCapture && !event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.setPointerCapture(event.pointerId)
      }
    },
    endMouseSwipe(event) {
      if (event.pointerType === 'mouse') this.endSwipe({ changedTouches: [this.mouseTouch(event)] })
    },
    cancelMouseSwipe(event) {
      if (event.pointerType === 'mouse') this.resetSwipe()
    },
    // #endif
    startSwipe(event) {
      if (this.leaving) return
      this.resetSwipe()
      if (event.touches.length !== 1) return
      const touch = event.touches[0]
      this._gesture = { id: touch.identifier, x: touch.clientX, y: touch.clientY }
    },
    moveSwipe(event) {
      if (!this._gesture) return
      if (event.touches.length !== 1) { this.resetSwipe(); return }
      const touch = event.touches[0]
      if (touch.identifier !== this._gesture.id) { this.resetSwipe(); return }
      const up = this._gesture.y - touch.clientY
      const sideways = Math.abs(this._gesture.x - touch.clientX)
      this.dragging = up > 8 && up > sideways * 1.25
      this.offset = this.dragging ? -Math.min(up * .42, 64) : 0
    },
    endSwipe(event) {
      if (!this._gesture) return
      const touch = Array.from(event.changedTouches || []).find(item => item.identifier === this._gesture.id)
      const up = touch ? this._gesture.y - touch.clientY : 0
      const sideways = touch ? Math.abs(this._gesture.x - touch.clientX) : 0
      this._gesture = null
      this.dragging = false
      if (up >= SWIPE_DISTANCE && up > sideways * 1.25) this.beginEntry()
      else this.offset = 0
    },
    resetSwipe() {
      this._gesture = null
      this.dragging = false
      this.offset = 0
    },
    beginEntry() {
      if (this.leaving) return
      this._gesture = null
      this.dragging = false
      this.leaving = true
      // WebViews that suppress transition events still complete navigation.
      this._exitTimer = setTimeout(() => this.openEntry(), EXIT_DURATION + 80)
    },
    finishTransition(event) {
      if (this.leaving && event.target === event.currentTarget && event.propertyName === 'opacity') this.openEntry()
    },
    openEntry() {
      if (this._opening) return
      clearTimeout(this._exitTimer)
      this._opening = true
      const fail = title => {
        this._opening = false
        this.leaving = false
        this.resetSwipe()
        uni.showToast({ title, icon: 'none' })
      }
      const completed = uni.getStorageSync(ONBOARDING_STORAGE_KEY)
      try {
        if (!completed) uni.setStorageSync(ONBOARDING_STORAGE_KEY, true)
      } catch (_) {
        fail(this.english ? 'Could not save. Please try again.' : '保存失败，请重试')
        return
      }
      uni.reLaunch({
        url: pendingClaim() ? CLAIM_ROUTE : HOME_URL,
        fail: () => {
          if (!completed) {
            try { uni.removeStorageSync(ONBOARDING_STORAGE_KEY) } catch (_) { /* Still allow retry. */ }
          }
          fail(this.english ? 'Could not open. Please try again.' : '页面打开失败，请重试')
        },
      })
    },
  },
}
</script>

<style scoped>
@font-face {
  font-family: 'Palace Welcome';
  src: url('/static/welcome-summer-palace/palace-welcome-bold.woff2') format('woff2');
  font-style: normal;
  font-weight: 700;
  font-display: swap;
}
.welcome {
  position: relative;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  touch-action: none;
  overscroll-behavior: none;
  user-select: none;
  background: #18283b;
  color: #fff;
}
.welcome-photo, .welcome-shade { position: absolute; inset: 0; pointer-events: none; }
.welcome-photo {
  background: url('/static/welcome-summer-palace/seventeen-arch-bridge.jpg') 46.5% top / auto 112% no-repeat;
}
.welcome-shade {
  background: linear-gradient(180deg, transparent 39%, rgba(12, 24, 41, .18) 59%, rgba(14, 29, 48, .56) 77%, rgba(13, 28, 48, .88) 100%);
  transition: background-color 460ms ease;
}
.welcome-shade.is-leaving { background-color: rgba(11, 22, 36, .3); }
.welcome-content {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 8.2%;
  opacity: 1;
  transform: translateY(var(--swipe-offset, 0px));
  transition: transform 230ms cubic-bezier(.19, 1, .35, 1);
}
.welcome-content.is-dragging { transition: none; }
.welcome-content.is-leaving {
  opacity: 0;
  transform: translateY(calc(var(--swipe-offset, 0px) - 110px));
  transition: transform var(--exit-duration) cubic-bezier(.22, .7, .3, 1), opacity var(--exit-duration) ease-in;
  pointer-events: none;
}
.welcome-type {
  margin-left: 7.2%;
  width: 79%;
}
.welcome-hi {
  display: block;
  width: min(43vw, 22vh);
  height: min(24.5vw, 12.54vh);
}
.welcome-line {
  display: flex;
  gap: clamp(7px, 2.5vw, 12px);
  align-items: center;
  margin-top: min(3.2vw, 1.6vh);
  white-space: nowrap;
}
.welcome-word {
  flex: none;
  width: min(39vw, 19vh);
  height: min(5.85vw, 2.85vh);
}
.welcome-destination {
  font: 700 min(8vw, 4vh)/1.16 'Palace Welcome', 'KaiTi', 'STKaiti', serif;
}
.welcome-destination.is-english {
  font: 800 min(4.6vw, 2.3vh)/1.16 system-ui, sans-serif;
  letter-spacing: -.04em;
}
.welcome-enter {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: max(56px, min(15vw, 7.5vh));
  margin: max(20px, min(13vw, 6.2vh)) auto 0;
  padding: 0;
  border: 0;
  border-radius: 16px;
  background: transparent;
  -webkit-tap-highlight-color: transparent;
}
.welcome-enter::after { border: 0; }
.welcome-enter[disabled] { background: transparent; }
.welcome-enter:focus-visible { outline: 2px solid #fff; outline-offset: 3px; }
.welcome-enter:active .welcome-chevron { transform: scale(.96); }
.welcome-arrow {
  display: flex;
  animation: welcome-float 2.15s ease-in-out infinite;
}
.welcome-chevron {
  display: block;
  width: min(11vw, 5.4vh);
  height: min(12.8vw, 6.28vh);
}
.welcome-content.is-dragging .welcome-arrow,
.welcome-content.is-leaving .welcome-arrow { animation-play-state: paused; }
@keyframes welcome-float {
  0%, 100% { transform: translateY(2px); }
  50% { transform: translateY(-6px); }
}
@media (min-aspect-ratio: 1/1) {
  .welcome-photo { background-size: cover; background-position: center; }
  .welcome-type { width: min(79%, 53vh); }
  .welcome-enter { margin-top: 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .welcome-arrow { animation: none; }
  .welcome-content { transform: none; transition: none; }
  .welcome-content.is-leaving { transform: none; transition: opacity 120ms ease; }
  .welcome-shade { transition: none; }
}
</style>
