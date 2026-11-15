<script setup lang="ts">
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import { locale } from '@/i18n'
import { lanOrigin } from '@/utils/lanOrigin'
const props = defineProps<{ url: string; label: string }>()
const visible = ref(false)
const code = ref('')
const failed = ref(false)
watch(() => [visible.value, props.url] as const, async ([open, url], _, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  code.value = ''
  failed.value = false
  if (!open) return
  try {
    const target = url.startsWith('/') ? new URL(url, await lanOrigin()).href : url
    const image = await QRCode.toDataURL(target, { width: 320, margin: 4 })
    if (current) code.value = image
  } catch {
    if (current) failed.value = true
  }
})
</script>
<template>
  <button type="button" class="phone-scan" @click="visible=true">{{ label }}</button>
  <el-dialog v-model="visible" :title="label" width="min(430px, 92vw)" align-center append-to-body destroy-on-close>
    <div class="phone-code">
      <img v-if="code" :src="code" :alt="label" />
      <p v-else-if="failed" role="alert">{{ locale === 'en' ? 'Could not generate code. Close and try again.' : '二维码生成失败，请关闭后重试。' }}</p>
      <p v-else role="status">{{ locale === 'en' ? 'Preparing code…' : '正在生成二维码…' }}</p>
    </div>
  </el-dialog>
</template>
<style scoped>
button.phone-scan { color:#4940ad; background:#f1f0fc; border:0; border-radius:10px; font:inherit; padding:8px 12px; margin:4px; cursor:pointer; }
.phone-code { display:grid; place-items:center; }
.phone-code img { width:min(100%,320px); height:auto; }
</style>
