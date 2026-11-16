<template><view class="xingyun-stage" :payload="payload" :change:payload="runtime.apply"><view id="tour-xingyun-avatar"></view></view></template>
<script>
export default {props:{payload:{type:Object,default:()=>({})}},methods:{runtimeEvent(event){this.$emit('state',event)}}}
</script>
<script module="runtime" lang="renderjs">
import {loadXingyunSdk} from '../common/xingyun-sdk.js'
import {AVATAR_QUALITY_STEPS,rightSizeAvatarCanvas,createAvatarQualityController} from '../common/avatar-performance.js'
let avatar=null,generation=0,timer=null,ready=false,gateway='',pending='',ownerRef=null
let destroyPending=Promise.resolve()
const quality=createAvatarQualityController()
let canvasTimer=null,lastCanvasSummary=''
function stopCanvasTimer(){clearTimeout(canvasTimer);canvasTimer=null}
function fitCanvas(){const container=document.getElementById('tour-xingyun-avatar'),canvas=container&&container.querySelector('canvas');if(!canvas)return false;const changed=rightSizeAvatarCanvas(canvas,{maxLongEdge:AVATAR_QUALITY_STEPS[quality.step]});const summary=canvas.width+'x'+canvas.height;if(changed||summary!==lastCanvasSummary){lastCanvasSummary=summary;console.info('[tour-xingyun] canvas',summary,'long-edge limit',AVATAR_QUALITY_STEPS[quality.step])}return changed}
function scheduleCanvasFit(delays=[0,400,1600]){stopCanvasTimer();const fit=index=>{if(index>=delays.length)return;canvasTimer=setTimeout(()=>{fitCanvas();fit(index+1)},delays[index])};fit(0)}
function release(){
  generation++;clearTimeout(timer);stopCanvasTimer();ready=false;gateway='';pending='';quality.reset();lastCanvasSummary=''
  const previous=avatar
  avatar=null
  if(previous)destroyPending=destroyPending.then(()=>previous.destroy()).catch(()=>{})
  return destroyPending
}
export default {
  methods:{
    // #ifdef H5
    closeBrowserAvatar(value){
      return this.apply(value, null, this.$ownerInstance)
    },
    // #endif
    async apply(value,old,owner){
      ownerRef=owner
      if(!value||value.command==='close'){
        const closing=release(),current=generation
        await closing
        const container=document.getElementById('tour-xingyun-avatar')
        if(current===generation&&container)container.innerHTML=''
        if(owner)owner.callMethod('runtimeEvent',{state:'closed',id:value&&value.id})
        return
      }
      if(value.command==='stop'){pending='';if(ready&&avatar)try{avatar.interactiveidle()}catch(e){}return}
      if(!value.gateway)return
      if(gateway===value.gateway){
        if(value.command==='speak'){pending=value.text||'';if(ready&&avatar){const text=pending;pending='';avatar.interactiveidle();avatar.speak(text,true,true)}}
        return
      }
      const closing=release(),version=generation
      await closing
      if(version!==generation)return
      gateway=value.gateway;pending=value.text||''
      const current=generation
      const report=(state,message)=>{if(current===generation&&ownerRef){if(state==='error')console.error('[tour-xingyun]',message);ownerRef.callMethod('runtimeEvent',{state,message,gateway:value.gateway})}}
      const fail=message=>{if(current!==generation)return;report('error',message);release()}
      const connected=()=>{
        if(current!==generation||ready)return
        ready=true;quality.reset();clearTimeout(timer);scheduleCanvasFit();report('connected')
        if(pending){const text=pending;pending='';avatar.speak(text,true,true)}
      }
      report('connecting')
      timer=setTimeout(()=>fail('星云连接超时，请检查网络后重试'),60000)
      try{
        await loadXingyunSdk()
        if(current!==generation)return
        const headers=value.accessToken?{'X-Tour-Access':value.accessToken}:{Authorization:'Bearer '+value.token}
        avatar=new window.XmovAvatar({containerId:'#tour-xingyun-avatar',appId:'server-proxy',appSecret:'server-proxy',gatewayServer:value.gateway,headers,
          hardwareAcceleration:'prefer-hardware',
          proxyWidget:{subtitle_on:()=>{},subtitle_off:()=>{}},
          onInitEvent:code=>{if(code===4000)connected()},
          onStateChange:state=>{if(state==='idle'||state==='interactive_idle')connected()},
          onVoiceStateChange:state=>{if(String(state).includes('start'))report('playing');if(String(state).includes('end'))report('ended')},
          onFPSUpdate:stats=>{
            if(current!==generation||!ready)return
            const previous=quality.step
            quality.sample(stats)
            if(previous!==quality.step){console.info('[tour-xingyun] quality',quality.step>previous?'sustained low fps':'recovered fps','long-edge limit',AVATAR_QUALITY_STEPS[quality.step]);scheduleCanvasFit([0,400])}
          },
          onMessage:error=>{
            const code=Number(error.code)
            if(!code||code===4000)return
            const message=code===5?'星云账号积分不足，请充值后重试':(error.message||'星云服务连接失败')
            fail(message+'（错误码：'+code+'）')
          },
        })
        await avatar.init({onDownloadProgress:progress=>report('progress','正在加载星云形象 '+Math.round(progress)+'%'),onClose:()=>{if(current===generation)fail('星云连接已断开，请重试')}})
        scheduleCanvasFit()
      }catch(e){if(current===generation)fail(e.message||'星云连接失败')}
    },
  },
  beforeUnmount(){release()},
}
</script>
<style scoped>
.xingyun-stage{position:absolute;inset:0;z-index:1;overflow:hidden;border-radius:24rpx;background:transparent}
#tour-xingyun-avatar{width:100%;height:100%;transform:translateX(0)}
</style>
