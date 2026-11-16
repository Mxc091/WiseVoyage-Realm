// A device preference, independent of account data and backend availability.
export const ONBOARDING_STORAGE_KEY = 'zhiyou.onboarding.v1.completed'
export const ONBOARDING_ROUTE = 'pages/onboarding/onboarding'
export const HOME_ROUTE = 'pages/tabs/tabs'
export const HOME_URL = '/' + HOME_ROUTE + '?tab=tour'

export function hasAppSession(loginProvider) {
  return !!uni.getStorageSync('token') && uni.getStorageSync('login_provider') === loginProvider
}
