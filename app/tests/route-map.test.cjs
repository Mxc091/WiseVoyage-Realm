const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm')
const root=path.resolve(__dirname,'..')
test('scrolling route detail uses a DOM map instead of an overlapping native map layer',()=>{
  const overview=fs.readFileSync(path.join(root,'components/RouteOverview.vue'),'utf8')
  assert.doesNotMatch(overview,/<map\s/,'Native map must not be embedded in the route scroll panel')
  assert.match(overview,/<RouteRoadMap\s/)
})
function renderer(){
  const fits=[],lines=[],observers=[],maps=[],pins=[],tileLayers=[]
  const map={attributionControl:{setPrefix(){},addAttribution(){}},on(){},getPane(){},createPane(){return{style:{}}},getZoom(){return 17},getSize(){return{x:390,y:250}},invalidateSize(){},stop(){},closePopup(){},fitBounds(bounds,options){fits.push({bounds,options})},remove(){this.removed=true}}
  const L={map(){maps.push(map);return map},control:{scale:()=>({addTo(){}})},layerGroup:()=>({addTo(){return this},clearLayers(){},remove(){}}),polyline(points,style){lines.push({points,style});return{on(){return this},addTo(){return this},bringToFront(){}}},divIcon:o=>o,latLngBounds:points=>points}
  L.polygon=()=>({addTo(){return this}})
  L.tileLayer=url=>{
    const handlers={}
    tileLayers.push({url,handlers})
    return {addTo(){return this},on(name,handler){handlers[name]=handler;return this}}
  }
  L.marker=(_point, options)=>{
    const record={options}
    pins.push(record)
    return {
      addTo(){return this},
      bindTooltip(node, tooltipOptions){record.tooltip={node, options:tooltipOptions};return this},
      bindPopup(node){record.popup=node;return this},
    }
  }
  class Observer{constructor(callback){this.callback=callback;observers.push(this)}observe(){}disconnect(){this.disconnected=true}}
  const win={L,__zhiyouLeafletReady:true,ResizeObserver:Observer,MutationObserver:Observer,requestAnimationFrame:()=>1,cancelAnimationFrame(){}},doc={body:{},createElement:()=>({textContent:'',children:[],appendChild(child){this.children.push(child)}})}
  const context={Promise,setTimeout,clearTimeout,JSON,Number,wanderBasemap:{labels:[]}};vm.createContext(context)
  const tileSettings = fs.readFileSync(path.join(root,'../shared/pedestrian-map.js'),'utf8').replace(/export /g,'')
  vm.runInContext(tileSettings,context)
  vm.runInContext(fs.readFileSync(path.join(root,'common/route-map-runtime.js'),'utf8').replace(/^import .*$/gm,'').replace(/export /g,'')+'\nglobalThis.api={createRouteMap,routeLineStyle}',context)
  const element={isConnected:true,addEventListener(){},removeEventListener(){}},events=[],controller=context.api.createRouteMap(element,e=>events.push(e),win,doc)
  const points=[{latitude:40,longitude:116},{latitude:40.07,longitude:116.03},{latitude:40.01,longitude:116.01}]
  const payload={data:{points,markers:[],polyline:[{points}],legIndexes:[0]},markerLabels:{},activeLeg:0,original:false,fitCounter:0}
  return{controller,payload,fits,lines,observers,maps,map,element,api:context.api,events,pins,tileLayers}
}
test('all road bends and stops determine padded bounds; choosing another leg preserves manual zoom',async()=>{
  const h=renderer();await h.controller.update(h.payload)
  assert.equal(h.fits.length,1);assert.equal(h.fits[0].bounds.length,3);assert.equal(h.fits[0].bounds[1][0],40.07)
  assert.deepEqual(Array.from(h.fits[0].options.padding),[28,28]);assert.equal(h.fits[0].options.maxZoom,18)
  await h.controller.update({...h.payload,activeLeg:1});assert.equal(h.fits.length,1)
  await h.controller.update({...h.payload,fitCounter:1});assert.equal(h.fits.length,2)
})
test('map strokes match the Web round caps, highlight and original-route colors',()=>{
  const h=renderer(),active=h.api.routeLineStyle(false,true),normal=h.api.routeLineStyle(false,false),original=h.api.routeLineStyle(true,false)
  assert.equal(active.color,'#513dbe');assert.equal(active.weight,6);assert.equal(active.lineCap,'round');assert.equal(active.lineJoin,'round')
  assert.equal(normal.color,'#a69acb');assert.equal(normal.weight,4);assert.equal(normal.opacity,.7);assert.equal(original.color,'#8b96ac')
  h.controller.destroy()
})
test('removing a scrolled dialog disposes its map and ignores a late renderer update',async()=>{
  const h=renderer();await h.controller.update(h.payload);h.element.isConnected=false;h.observers[0].callback()
  assert.equal(h.map.removed,true);assert.ok(h.observers.every(o=>o.disconnected));await h.controller.update(h.payload);assert.equal(h.maps.length,1)
})
test('named route stops show a permanent label and details, while unnamed pins disclose neither',async()=>{
  const h=renderer()
  const markers=h.payload.data.points.slice(0,2).map((point,index)=>({...point,id:index+1}))
  await h.controller.update({
    ...h.payload, data:{...h.payload.data,markers},
    markerLabels:{1:{name:'玉澜堂',lines:['步行接入点','预计停留 15 分钟']}},
  })
  assert.equal(h.pins[0].tooltip.node.textContent,'玉澜堂')
  assert.equal(h.pins[0].tooltip.options.permanent,true)
  assert.deepEqual(h.pins[0].popup.children.map(node=>node.textContent),['玉澜堂','步行接入点','预计停留 15 分钟'])
  assert.equal(h.pins[1].options.interactive,false)
  assert.equal(h.pins[1].tooltip,undefined)
  assert.equal(h.pins[1].popup,undefined)
})
test('ordinary wander maps load detailed tiles and blind previews use a label-controlled basemap',async()=>{
  const normal=renderer()
  await normal.controller.update({...normal.payload,wander:true,detailed:true})
  assert.match(normal.tileLayers[0].url,/tile.openstreetmap.org/)
  assert.equal(normal.events.at(-1).state,'loading')
  const {handlers}=normal.tileLayers[0]
  handlers.loading()
  handlers.tileerror()
  handlers.load()
  await normal.controller.update({...normal.payload,wander:true,detailed:true,activeLeg:1})
  assert.equal(normal.events.at(-1).state,'tiles-error')
  handlers.loading()
  handlers.tileload()
  handlers.load()
  assert.equal(normal.events.at(-1).state,'ready')

  const blind=renderer()
  await blind.controller.update({...blind.payload,wander:true,compact:true,blind:true})
  assert.equal(blind.tileLayers.length,0)
  assert.equal(blind.events.at(-1).state,'ready')
})
