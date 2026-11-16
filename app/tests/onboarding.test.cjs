const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '..')

function harness(file, initial = {}, route = '') {
  const storage = { ...initial }, navigation = [], toasts = [], timers = []
  const context = { console, LOGIN_PROVIDER: 'password', LANGUAGE_STORAGE_KEY: 'language',
    setTimeout: (fn, delay) => { const timer = { fn, delay, cancelled: false }; timers.push(timer); return timer },
    clearTimeout: timer => { if (timer) timer.cancelled = true },
    getCurrentPages: () => route ? [{ route }] : [],
    uni: {
      getStorageSync: key => storage[key],
      setStorageSync: (key, value) => { storage[key] = value },
      removeStorageSync: key => { delete storage[key] },
      reLaunch: options => navigation.push(options),
      showToast: options => toasts.push(options),
    },
  }
  vm.createContext(context)
  const helpers = fs.readFileSync(path.join(root, 'common/onboarding.js'), 'utf8').replace(/export /g, '')
  vm.runInContext(helpers, context)
  vm.runInContext(fs.readFileSync(path.join(root, 'common/station-claim.js'), 'utf8').replace(/export /g, ''), context)
  const script = fs.readFileSync(path.join(root, file), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  vm.runInContext(script.replace(/^import .*$/gm, '').replace('export default', 'globalThis.options ='), context)
  const options = context.options
  const state = options.data ? options.data() : {}
  for (const [key, fn] of Object.entries(options.methods || {})) state[key] = fn.bind(state)
  for (const [key, fn] of Object.entries(options.computed || {})) Object.defineProperty(state, key, { get: () => fn.call(state) })
  return { context, options, state, storage, navigation, toasts, timers }
}

test('first launch is visible before authentication, including resumed old routes', () => {
  const first = harness('App.vue', {}, 'pages/auth/auth')
  first.options.onShow.call(first.state)
  assert.equal(first.navigation[0].url, '/pages/onboarding/onboarding')
  for (const route of ['', 'pages/onboarding/onboarding']) {
    const intro = harness('App.vue', {}, route)
    intro.options.onShow.call(intro.state)
    assert.equal(intro.navigation.length, 0, 'do not relaunch the default first page twice')
  }
})

const page = 'pages/onboarding/onboarding.vue'
const key = 'zhiyou.onboarding.v1.completed'
const home = '/pages/tabs/tabs?tab=tour'
const finger = (x, y, id = 1) => ({ clientX: x, clientY: y, identifier: id })
function swipe(s, end) {
  s.startSwipe({ touches: [finger(180, 680)] })
  s.moveSwipe({ touches: [end] })
  s.endSwipe({ changedTouches: [end] })
}

test('an upward swipe moves the content and enters the real home once after the exit', () => {
  const h = harness(page)
  const s = h.state
  s.startSwipe({ touches: [finger(180, 680)] })
  s.moveSwipe({ touches: [finger(185, 580)] })
  assert.equal(s.dragging, true)
  assert.ok(s.offset < 0)
  s.endSwipe({ changedTouches: [finger(185, 580)] })
  s.beginEntry()
  assert.equal(s.leaving, true)
  assert.equal(h.navigation.length, 0)
  assert.equal(h.timers.length, 1)
  const target = {}
  s.finishTransition({ target, currentTarget: target, propertyName: 'opacity' })
  h.timers[0].fn()
  assert.equal(h.navigation.length, 1)
  assert.equal(h.navigation[0].url, home)
  assert.equal(h.storage[key], true)
})

test('short, horizontal, downward, and multi-touch gestures do not open home', () => {
  const h = harness(page)
  const s = h.state
  for (const touch of [finger(182, 642), finger(20, 610), finger(181, 770), finger(180, 560, 2)]) {
    swipe(s, touch)
    assert.equal(s.offset, 0)
  }
  s.startSwipe({ touches: [finger(180, 680), finger(240, 700, 2)] })
  s.endSwipe({ changedTouches: [finger(180, 580)] })
  assert.equal(h.timers.length, 0)
  assert.equal(h.storage[key], undefined)
})

test('arrow fallback, returning users, and pending station claims resolve the appropriate entry', () => {
  const guest = harness(page)
  guest.state.beginEntry()
  guest.timers[0].fn()
  assert.equal(guest.navigation[0].url, home)
  const returning = harness(page, { [key]: true, token: 'existing', login_provider: 'password', language: 'en' })
  returning.options.onLoad.call(returning.state)
  assert.equal(returning.navigation[0].url, home)
  assert.equal(returning.storage.token, 'existing')
  assert.equal(returning.state.english, true)
  const claim = harness(page, { 'station-pending-claim': { token: 'saved' } })
  claim.state.beginEntry()
  claim.timers[0].fn()
  assert.equal(claim.navigation[0].url, '/pages/claim/claim')
})

test('returning guests may open home while other App pages still check sign-in', () => {
  const guest = harness('App.vue', { [key]: true }, 'pages/tabs/tabs')
  guest.options.onShow.call(guest.state)
  assert.equal(guest.navigation.length, 0)
  const protectedPage = harness('App.vue', { [key]: true }, 'pages/tour/tour')
  protectedPage.options.onShow.call(protectedPage.state)
  assert.equal(protectedPage.navigation[0].url, '/pages/auth/auth')
})

test('unload cancels the transition and a failed navigation can be retried', () => {
  const h = harness(page)
  h.state.beginEntry()
  h.options.onUnload.call(h.state)
  assert.equal(h.timers[0].cancelled, true)
  const retry = harness(page)
  retry.state.beginEntry()
  retry.timers[0].fn()
  retry.navigation[0].fail()
  assert.equal(retry.state.leaving, false)
  assert.equal(retry.storage[key], undefined)
  retry.state.beginEntry()
  retry.timers[1].fn()
  assert.equal(retry.navigation[1].url, home)
})
