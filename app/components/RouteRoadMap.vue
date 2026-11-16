<template>
  <view class="route-map-wrapper" :class="{'map-expanded':expanded,'map-wander':wander,'map-compact':compact}">
    <view class="route-dom-map" :map-options="payload" :change:map-options="renderer.update">
      <view :id="mapId" class="route-map-canvas"></view>
      <text v-if="wander" class="route-map-north">↑ {{ t('北') }}</text>
    </view>
    <text v-if="loading" class="route-map-message">{{ t('地图加载中…') }}</text>
    <view v-if="error" class="route-map-message"><text>{{ t(error) }}</text><button @tap="retry">{{ t('重试') }}</button></view>
  </view>
</template>
<script>
// #ifdef H5
import { createRouteMap } from '../common/route-map-runtime.js'
// #endif
export default {
  props:{expanded:Boolean,data:Object,original:Boolean,activeLeg:Number,currentMarker:Number,markerLabels:Object,steps:Array,wander:Boolean,compact:Boolean,blind:Boolean,detailed:Boolean},emits:['leg','interacting'],
  data(){let assetBase='./static/vendor/leaflet/'
    // #ifdef H5
    assetBase=(import.meta.env.BASE_URL||'/')+'static/vendor/leaflet/'
    // #endif
    return{assetBase,mapId:'route-road-'+Date.now()+'-'+Math.random().toString(36).slice(2,9),fitCounter:0,revision:0,loading:true,error:''}},
  computed:{payload(){return{mapId:this.mapId,assetBase:this.assetBase,data:this.data,original:this.original,activeLeg:this.activeLeg,currentMarker:this.currentMarker,markerLabels:this.markerLabels||{},steps:this.steps,wander:this.wander,compact:this.compact,blind:this.blind,detailed:this.detailed,fitCounter:this.fitCounter,revision:this.revision,zoomIn:this.t('放大地图'),zoomOut:this.t('缩小地图'),mapTerms:this.mapTerms}},
    mapTerms(){return this.wander ? Object.fromEntries(['湖面','山地','洗手间','公交站','停车场','码头','园区导览图','园林步道'].map(term=>[term,this.t(term)])) : {}}
  },
  watch:{payload:{deep:true,handler(value){
    // #ifdef H5
    this._mapController?.update(value)
    // #endif
  }}},
  mounted(){
    // #ifdef H5
    this._mapController=createRouteMap(document.getElementById(this.mapId),this.mapStatus)
    this._mapController.update(this.payload)
    // #endif
  },
  beforeUnmount(){this._mapDisposed=true
    // #ifdef H5
    this._mapController?.destroy()
    // #endif
  },
  methods:{
    mapStatus(event) {
      if (this._mapDisposed) return
      if (event.state==='gesture') { this.$emit('interacting',event.active); return }
      if (event.state==='leg') { this.$emit('leg',event.index); return }
      this.loading=event.state==='loading'
      this.error=event.state==='error'?event.message:event.state==='tiles-error'?'底图加载失败，路线仍可查看':''
    },
    refit(){this.fitCounter++},
    retry(){this.loading=true;this.error='';this.revision++;this.fitCounter++},
  },
}
</script>
<script module="renderer" lang="renderjs">
import { createRouteMap } from '../common/route-map-runtime.js'
export default {methods:{
refit(){
  // #ifdef APP-PLUS
  this._controller?.fitAll()
  // #endif
},
update(value,old,owner){
  // #ifdef APP-PLUS
  if(!value?.mapId)return
  if(this._mapId!==value.mapId){this._controller?.destroy();this._controller=null;this._mapId=value.mapId}
  cancelAnimationFrame(this._pendingFrame)
  let attempts=0
  const render=()=>{if(this._mapId!==value.mapId)return;const element=document.getElementById(value.mapId)
    if(!element){if(++attempts<8)this._pendingFrame=requestAnimationFrame(render);return}
    if(!this._controller)this._controller=createRouteMap(element,event=>owner.callMethod('mapStatus',event))
    this._controller.update(value)
  }
  render()
  // #endif
}}}
</script>
<style scoped>
.route-map-wrapper{margin-top:20rpx;min-width:0;position:relative}.route-dom-map{height:460px;height:min(50vh,460px);min-height:300px;border-radius:18rpx;overflow:hidden;position:relative;isolation:isolate;background:#eff1f6}.route-map-canvas{width:100%;height:100%;position:relative;z-index:0}.route-map-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12rpx;margin-top:12rpx;color:var(--ng-secondary);font-size:22rpx;flex-wrap:wrap}.route-map-fit{margin:0;padding:3rpx 16rpx;line-height:2;font-size:24rpx;border-radius:12rpx;background:#eee9f8;color:#5d469e}.route-map-message{display:block;color:var(--ng-secondary);font-size:24rpx;line-height:1.7;margin:12rpx 0}.route-map-message button{font-size:24rpx;margin:10rpx 0;background:#f2eef8;color:#5d469e}
.map-expanded .route-dom-map{height:78vh;min-height:240px;max-height:calc(100vh - 150px - var(--status-bar-height));border-radius:18px}
.route-dom-map,.route-map-canvas{touch-action:none;overscroll-behavior:contain}
.map-wander .route-dom-map,.map-wander :deep(.leaflet-container){background:#e8ecde}
.map-wander .route-dom-map,.map-wander .route-map-canvas.leaflet-container { touch-action:pan-y; overscroll-behavior:auto; }
.route-map-north { position:absolute; z-index:1; top:8px; left:8px; padding:3px 6px; border-radius:6px; background:#ffffffeb; color:#40474b; font:400 11px/1.4 var(--app-font-family); pointer-events:none; }
.route-map-canvas :deep(.wander-context-label) { border:none; padding:0; background:none; box-shadow:none; color:#526055; font:400 11px/1.4 var(--app-font-family); text-shadow:0 0 3px #fff, 0 1px 2px #fff; }
.route-map-canvas :deep(.wander-context-label::before) { display:none; }
.route-map-canvas :deep(.wander-context-label.terrain) { color:#34687d; letter-spacing:.08em; }
.route-map-canvas :deep(.wander-context-label.facility) { color:#465d60; }
.map-compact :deep(.wander-context-label) { font-size:10px; }
.map-wander :deep(.leaflet-control-scale-line) { border-color:#667471; background:#ffffffe0; color:#46544f; font-size:9px; }
.map-wander .route-map-canvas :deep(.route-map-pin){width:40px;height:40px;font-size:17px;background:#6650b8;border-width:3px}
.map-wander .route-map-canvas :deep(.route-map-pin.gate){background:#23816b}
.map-compact.map-wander .route-map-canvas :deep(.route-map-pin){width:26px;height:26px;font-size:12px;border-width:2px;box-shadow:0 1px 4px #4b3c6b33}
.map-compact :deep(.leaflet-control-attribution){font-size:9px}
.route-map-canvas :deep(.route-stop-label) {
  padding: 3px 6px;
  border: 1px solid #e8e0f1;
  border-radius: 8px;
  background: #fffffff7;
  box-shadow: 0 2px 6px #46385920;
  color: #34274f;
  font: 400 11px/1.35 var(--app-font-family);
}
.route-map-canvas :deep(.route-stop-label::before) { display: none; }
.map-compact .route-map-canvas :deep(.route-stop-label) { padding: 2px 4px; font-size: 10px; }
.route-map-canvas :deep(.route-stop-popup strong) { display: block; margin-bottom: 4px; font-weight: 600; }
</style>
<style scoped>
.route-map-canvas :deep(.route-map-pin){display:grid;place-items:center;box-sizing:border-box;width:30px;height:30px;border:2.5px solid #fff;border-radius:50%;box-shadow:0 2px 8px #50428155;background:#6652bd;color:#fff;font:400 12px var(--app-font-family)}.route-map-canvas :deep(.route-map-pin.current){background:#23816b}.route-map-canvas :deep(.route-map-pin.gate){border-radius:10px;background:#23816b;font-size:18px}.route-map-canvas :deep(.leaflet-control-zoom a){color:#5b4697}.route-map-canvas :deep(.leaflet-popup-content){font:14px/1.6 var(--app-font-family);overflow-wrap:anywhere}.route-map-canvas :deep(.leaflet-control-container){font-family:var(--app-font-family)}
</style>
