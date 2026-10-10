/* 共同导航只分发章节请求；各等级自行实现切换。 */
(() => {
  const tier = document.body.dataset.tier;
  const sections = [...document.querySelectorAll('[data-chapter]')];
  const links = [...document.querySelectorAll('[data-nav]')];
  let current = 0;
  function mark(index) {
    current = index;
    links.forEach((link, i) => { if(i === index) link.setAttribute('aria-current','step'); else link.removeAttribute('aria-current'); });
  }
  function go(index) {
    index = Math.max(0, Math.min(sections.length - 1, index));
    if(tier === 'T3') { document.dispatchEvent(new CustomEvent('showcase:navigate',{detail:{index}})); return; }
    mark(index);
    sections[index].scrollIntoView({behavior:tier === 'T2' && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'instant'});
    history.replaceState(null,'','#'+sections[index].id);
  }
  links.forEach((link,i) => link.addEventListener('click', event => {event.preventDefault();go(i);}));
  document.addEventListener('keydown', event => {
    if(event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || /INPUT|TEXTAREA|SELECT|BUTTON|A/.test(event.target.tagName) || event.target.isContentEditable) return;
    const delta = ({ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1,' ':event.shiftKey ? -1 : 1})[event.key];
    if(delta !== undefined) {event.preventDefault();go(current+delta);}
  });
  document.addEventListener('showcase:arrived',event => mark(event.detail.index));
  if(tier !== 'T3') {
    let pending = false;
    addEventListener('scroll',() => {if(pending)return;pending=true;requestAnimationFrame(() => {pending=false;mark(sections.reduce((best,section,i) => Math.abs(section.getBoundingClientRect().top) < Math.abs(sections[best].getBoundingClientRect().top) ? i : best,0));});},{passive:true});
    const initial = sections.findIndex(section => '#'+section.id === location.hash);
    if(initial >= 0) go(initial);
  }
  mark(current);
})();
