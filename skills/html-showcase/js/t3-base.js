/* 动态导入使网络失败也能进入静态摘要；全场仅一个 rAF 循环。 */
(async () => {
  const fallback=document.getElementById('fallback'), overlay=document.querySelector('.overlay'), stage=document.getElementById('stage');
  let renderer, frame=0, failed=false;
  function fail(){failed=true;cancelAnimationFrame(frame);overlay.hidden=true;stage.hidden=true;fallback.hidden=false;document.getElementById('fallback-status').textContent='三维场景不可用，请阅读静态摘要。';renderer?.dispose();}
  try {
    if(!document.createElement('canvas').getContext('webgl2')) throw new Error('设备不支持三维渲染');
    const THREE=await import('three');
    const css=getComputedStyle(document.documentElement), color=name=>new THREE.Color(css.getPropertyValue(name).trim());
    renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);stage.append(renderer.domElement);
    const scene=new THREE.Scene();scene.fog=new THREE.FogExp2(color('--bg'),.035);
    const camera=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,.1,120);
    scene.add(new THREE.HemisphereLight(0xffffff,0x34394b,1.8));
    const key=new THREE.DirectionalLight(0xffffff,2.5);key.position.set(4,6,5);scene.add(key);
    [0x44ddff,0xff5599].forEach((value,i)=>{const rim=new THREE.DirectionalLight(value,1.2);rim.position.set(i? -5:5,2,-4);scene.add(rim);});
    const objects=[];
    for(let i=0;i<3;i++){const object=new THREE.Mesh(new THREE.IcosahedronGeometry(.85,1),new THREE.MeshStandardMaterial({color:color('--accent'),roughness:.35,metalness:.25,emissive:color('--accent'),emissiveIntensity:.08}));object.position.set((i-1)*3,0,0);object.userData.label=['待补充：开场物体','待补充：核心物体','待补充：总结物体'][i];scene.add(object);objects.push(object);}
    /* 粒子数量严格小于两万；共享缓冲，不逐粒子更新。 */
    const particleCount=1800, positions=new Float32Array(particleCount*3);
    for(let i=0;i<positions.length;i++)positions[i]=(Math.random()-.5)*40;
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));
    const particles=new THREE.Points(geometry,new THREE.PointsMaterial({color:color('--accent'),size:.035,transparent:true,opacity:.45}));scene.add(particles);
    const waypoints=objects.map(object=>({target:object.position.clone(),position:object.position.clone().add(new THREE.Vector3(0,1.5,7))}));
    const target=new THREE.Vector3(), orbit=new THREE.Spherical(), raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2(9,9);
    const label=document.getElementById('label'), panel=document.getElementById('panel'), tourButton=document.getElementById('tour');
    let current=0, flight=null, hovered=null, pointerDirty=false, lastRay=0, drag=null, tour=false, nextTour=0, lastTime=0, hiddenAt=0;
    camera.position.copy(waypoints[0].position);target.copy(waypoints[0].target);camera.lookAt(target);
    function stopTour(){tour=false;tourButton.textContent='开始导览';tourButton.setAttribute('aria-pressed','false');}
    function hover(object){if(hovered===object)return;if(hovered){hovered.scale.setScalar(1);hovered.material.emissiveIntensity=.08;}hovered=object;label.hidden=!object;if(object){object.scale.setScalar(1.05);object.material.emissiveIntensity=.65;label.textContent=object.userData.label;}}
    function fly(index){if(flight || failed)return;index=Math.max(0,Math.min(2,index));hover(null);panel.hidden=true;drag=null;flight={start:performance.now(),duration:1500,index,from:camera.position.clone(),fromTarget:target.clone()};overlay.classList.add('flying');}
    document.addEventListener('showcase:navigate',event=>fly(event.detail.index));
    const canvas=renderer.domElement;
    function locate(event){const rect=canvas.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);pointerDirty=true;}
    canvas.addEventListener('pointermove',event=>{locate(event);if(!drag || flight)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;drag.distance+=Math.abs(dx)+Math.abs(dy);orbit.setFromVector3(camera.position.clone().sub(target));orbit.theta-=dx*.006;orbit.phi=THREE.MathUtils.clamp(orbit.phi+dy*.006,.2,Math.PI-.2);camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(orbit));camera.lookAt(target);drag.x=event.clientX;drag.y=event.clientY;});
    canvas.addEventListener('pointerdown',event=>{if(flight || !event.isPrimary || event.button!==0)return;locate(event);drag={x:event.clientX,y:event.clientY,distance:0,id:event.pointerId};canvas.setPointerCapture(event.pointerId);});
    canvas.addEventListener('pointerup',event=>{if(!drag || drag.id!==event.pointerId)return;const clicked=drag.distance<6;drag=null;if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);if(clicked && !flight){locate(event);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(objects)[0]?.object;if(hit){panel.hidden=false;panel.querySelector('h2').textContent=hit.userData.label;}}});
    canvas.addEventListener('pointercancel',()=>{drag=null;});canvas.addEventListener('pointerleave',()=>{if(!drag){pointer.set(9,9);hover(null);}});
    canvas.addEventListener('wheel',event=>{event.preventDefault();if(flight)return;orbit.setFromVector3(camera.position.clone().sub(target));orbit.radius=THREE.MathUtils.clamp(orbit.radius*Math.exp(event.deltaY*.001),3,16);camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(orbit));camera.lookAt(target);pointerDirty=true;},{passive:false});
    /* 捕获阶段先退出导览，随后才处理同一个输入的导航或操作。 */
    ['pointerdown','pointermove','wheel','keydown','click','touchstart'].forEach(type=>document.addEventListener(type,event=>{if(!tour)return;if(event.target===tourButton && ['pointerdown','click','touchstart'].includes(type))return;stopTour();},{capture:true,passive:true}));
    tourButton.addEventListener('click',()=>{if(tour){stopTour();return;}tour=true;tourButton.textContent='退出导览';tourButton.setAttribute('aria-pressed','true');if(!flight)fly((current+1)%3);nextTour=Infinity;});
    document.getElementById('reset').addEventListener('click',()=>fly(current));document.getElementById('close-panel').addEventListener('click',()=>panel.hidden=true);
    function tick(now){if(failed || document.hidden)return;try{const dt=lastTime?Math.min((now-lastTime)/1000,.05):0;lastTime=now;
      if(flight){const progress=Math.min(1,(now-flight.start)/flight.duration),ease=progress*progress*(3-2*progress),point=waypoints[flight.index];camera.position.lerpVectors(flight.from,point.position,ease);target.lerpVectors(flight.fromTarget,point.target,ease);camera.lookAt(target);if(progress===1){current=flight.index;flight=null;document.querySelectorAll('[data-chapter]').forEach((section,i)=>section.hidden=i!==current);overlay.classList.remove('flying');document.dispatchEvent(new CustomEvent('showcase:arrived',{detail:{index:current}}));nextTour=now+4500;pointerDirty=true;}}
      if(tour && !flight && now>=nextTour){fly((current+1)%3);nextTour=Infinity;}
      const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
      if(!reduced){particles.rotation.y+=dt*.025;objects.forEach(object=>object.rotation.y+=dt*.15);pointerDirty=true;}
      if(!flight && !drag && pointerDirty && now-lastRay>=50){lastRay=now;pointerDirty=false;raycaster.setFromCamera(pointer,camera);hover(raycaster.intersectObjects(objects)[0]?.object || null);}
      if(hovered){const projected=hovered.position.clone().project(camera);label.style.left=`${THREE.MathUtils.clamp((projected.x+1)*innerWidth/2,8,Math.max(8,innerWidth-label.offsetWidth-8))}px`;label.style.top=`${THREE.MathUtils.clamp((-projected.y+1)*innerHeight/2,8,innerHeight-50)}px`;}
      renderer.render(scene,camera);frame=requestAnimationFrame(tick);
    }catch(error){console.error('三维展示已降级',error);fail();}}
    addEventListener('resize',()=>{if(failed)return;try{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);pointerDirty=true;}catch{fail();}});
    canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();fail();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){hiddenAt=performance.now();cancelAnimationFrame(frame);lastTime=0;}else if(!failed){const pause=performance.now()-hiddenAt;if(flight)flight.start+=pause;if(Number.isFinite(nextTour))nextTour+=pause;frame=requestAnimationFrame(tick);}});
    fallback.hidden=true;overlay.hidden=false;if(!document.hidden)frame=requestAnimationFrame(tick);
  }catch(error){console.error('三维展示初始化失败',error);fail();}
})();
