/* ===================================================================
   Bereshit Judaica — Admin Dashboard
   Vanilla JS. Every management action here calls the real Flask API
   (via shared/data-service.js), which is the only thing that talks to
   MongoDB. There is no mock/demo path — if an action can't reach the
   API it fails with a visible error, it never pretends to succeed.
   =================================================================== */
(function(){
  'use strict';

  const $ = (sel,ctx=document)=>ctx.querySelector(sel);
  const $$ = (sel,ctx=document)=>Array.from(ctx.querySelectorAll(sel));
  const fmt = n => '₪' + Number(n).toLocaleString('he-IL');
  const fmtDate = d => { const dt=new Date(d); return dt.toLocaleDateString('he-IL',{day:'numeric',month:'short',year:'numeric'}); };
  const initials = name => name.trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('');
  function escAttr(str){
    return String(str==null?'':str).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  /* ---------------- Toast ---------------- */
  let toastTimer;
  function toast(msg){
    const el = $('#toast');
    $('#toastText').textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(()=>el.classList.remove('show'), 2600);
  }

  /* ---------------- Field validation helpers (shared by every modal) ---------------- */
  function setFieldError(id, msg){
    const el = $('#'+id); if(el) el.classList.add('invalid');
    const err = $('#'+id+'Error'); if(err) err.textContent = msg;
  }
  function clearFieldErrors(ids){
    ids.forEach(id=>{
      const el = $('#'+id); if(el) el.classList.remove('invalid');
      const err = $('#'+id+'Error'); if(err) err.textContent = '';
    });
  }
  function withBusy(btn, busyLabel, fn){
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = busyLabel;
    return Promise.resolve(fn()).finally(()=>{ btn.disabled = false; btn.textContent = original; });
  }

  /* ---------------- Thumbnails ---------------- */
  // Category icon placeholder — used for category rows and as a fallback
  // wherever a product has no real photo.
  function thumbHtml(cat, size){
    const gold = ['תכשיטים','הבדלה'].includes(cat);
    return `<div class="thumb${gold?' gold':''}" style="width:${size}px;height:${size}px"><svg viewBox="0 0 24 24">${catIcon(cat)}</svg></div>`;
  }
  // Real product photo when the product has one; otherwise the category
  // placeholder above. This is what every product-representing surface
  // (table, grid, best-sellers, low-stock, order lines) should use.
  function productImgHtml(p, size){
    if(p && p.image){
      return `<div class="thumb" style="width:${size}px;height:${size}px"><img src="${escAttr(p.image)}" alt="${escAttr(p.name||'')}" onerror="this.remove()"></div>`;
    }
    return thumbHtml(p ? p.cat : null, size);
  }

  /* ---------------- Category select options (kept in sync with real CATEGORIES) ---------------- */
  function categoryLabels(){ return CATEGORIES.map(c=>c.name); }
  function refreshCategorySelects(){
    const opts = categoryLabels().map(c=>`<option value="${escAttr(c)}">${c}</option>`).join('');
    const filter = $('#productCatFilter');
    if(filter) filter.innerHTML = `<option value="">כל הקטגוריות</option>` + opts;
  }

  /* ================= Sidebar / Navigation ================= */
  const PAGE_TITLES = {
    dashboard:{ h:'לוח בקרה', c:'סקירה כללית של החנות' },
    products:{ h:'מוצרים', c:'ניהול קטלוג המוצרים' },
    orders:{ h:'הזמנות', c:'מעקב וניהול הזמנות לקוחות' },
    customers:{ h:'לקוחות', c:'ניהול לקוחות ופרטי קשר' },
    categories:{ h:'קטגוריות', c:'ניהול קטגוריות מוצרים' },
    inventory:{ h:'מלאי', c:'מעקב וניהול מלאי מוצרים' },
    promotions:{ h:'מבצעים', c:'קופונים והנחות פעילים' },
    content:{ h:'תוכן', c:'ניהול תוכן אתר החנות' },
    settings:{ h:'הגדרות', c:'הגדרות כלליות של החנות' },
  };

  function navigateTo(page){
    $$('.page').forEach(p=>p.classList.toggle('active', p.dataset.page===page));
    $$('.nav-item').forEach(n=>n.classList.toggle('active', n.dataset.nav===page));
    const meta = PAGE_TITLES[page] || PAGE_TITLES.dashboard;
    $('#topbarTitle').textContent = meta.h;
    $('#topbarCrumb').textContent = 'ניהול / ' + meta.h;
    document.title = meta.h + ' | פאנל ניהול — בראשית יודאיקה';
    closeMobileSidebar();
    $('#content').scrollTo?.({top:0});
    window.scrollTo({top:0,behavior:'auto'});
    if(page==='dashboard') renderChart(currentPeriod);
  }

  function initSidebarNav(){
    $$('.nav-item').forEach(item=>{
      item.addEventListener('click', ()=> navigateTo(item.dataset.nav));
    });
    $$('[data-nav-inline]').forEach(item=>{
      item.addEventListener('click', ()=> navigateTo(item.dataset.navInline));
    });
    $('#collapseBtn').addEventListener('click', ()=>{
      $('#sidebar').classList.toggle('collapsed');
    });
    $('#mobileMenuBtn').addEventListener('click', ()=>{
      $('#sidebar').classList.add('mobile-open');
      $('#sidebarScrim').classList.add('show');
    });
    $('#sidebarScrim').addEventListener('click', closeMobileSidebar);
  }
  function closeMobileSidebar(){
    $('#sidebar').classList.remove('mobile-open');
    $('#sidebarScrim').classList.remove('show');
  }

  /* ================= KPIs (all real, computed from loaded API data) ================= */
  function renderKPIs(){
    const totalSales = ORDERS.reduce((s,o)=>s + (o.status!=='בוטל'?o.total:0),0);
    const needsAttention = PRODUCTS.filter(p=>p.stock<=p.threshold).length;
    const salesTrend = computeSalesTrend();
    const ordersTrend = computeOrdersTrend();
    const newCustomers = computeNewCustomersThisMonth();

    const kpis = [
      { label:'סה"כ מכירות', value:fmt(totalSales), trend:salesTrend.text, up:salesTrend.up, icon:iconRevenue(), cls:'' },
      { label:'הזמנות', value:ORDERS.length, trend:ordersTrend.text, up:ordersTrend.up, icon:iconOrders(), cls:'gold' },
      { label:'מוצרים', value:PRODUCTS.length, trend:null, icon:iconProducts(), cls:'' },
      { label:'לקוחות', value:CUSTOMERS.length, trend: newCustomers>0 ? `+${newCustomers} החודש` : null, up:true, icon:iconCustomers(), cls:'gold' },
      { label:'מלאי דורש טיפול', value:needsAttention, trend: needsAttention>0 ? 'דורש טיפול' : 'הכל תקין', up:needsAttention===0, icon:iconAlert(), cls: needsAttention>0 ? 'danger' : '' },
    ];
    $('#kpiGrid').innerHTML = kpis.map(k=>`
      <div class="kpi-card">
        <div class="kpi-top">
          <div class="kpi-icon ${k.cls}"><svg class="icon" viewBox="0 0 24 24">${k.icon}</svg></div>
          ${k.trend ? `<div class="kpi-trend ${k.up?'up':'down'}">${k.up?'▲':'▼'} ${k.trend}</div>` : ''}
        </div>
        <div class="kpi-value">${k.value}</div>
        <div class="kpi-label">${k.label}</div>
      </div>
    `).join('');
  }
  function iconRevenue(){return '<circle cx="12" cy="12" r="9"/><path d="M9 15s.8 1.2 3 1.2 3-1 3-2-1.3-1.6-3-2-3-1-3-2 1.3-2 3-2 3 1.2 3 1.2" stroke-linecap="round"/>';}
  function iconOrders(){return '<path d="M6 8h12l-1 12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L6 8Z" stroke-linejoin="round"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>';}
  function iconProducts(){return '<path d="M3 8l9-5 9 5-9 5-9-5Z" stroke-linejoin="round"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>';}
  function iconCustomers(){return '<circle cx="9" cy="8" r="3.4"/><path d="M2.5 20c1-3.5 3.6-5.5 6.5-5.5s5.5 2 6.5 5.5"/><circle cx="17.5" cy="7.5" r="2.6"/><path d="M15.5 13.3c2.3.2 4.2 1.9 5 4.7"/>';}
  function iconAlert(){return '<path d="M12 3 2 20h20L12 3Z" stroke-linejoin="round"/><path d="M12 10v4"/><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none"/>';}

  /* ================= Sales chart (real, from ORDERS — see computeSalesSeries in data.js) ================= */
  let currentPeriod = '7d';
  function initChartControls(){
    $$('#periodSelector button').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        $$('#periodSelector button').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        currentPeriod = btn.dataset.period;
        renderChart(currentPeriod);
      });
    });
  }
  function renderChart(period){
    const series = computeSalesSeries(period);
    const pts = series.points;
    const w = 620, h = 220, pad = 10;
    const max = Math.max(...pts), min = Math.min(...pts);
    const range = (max-min) || 1;
    const stepX = (w - pad*2) / (pts.length-1);
    const coords = pts.map((v,i)=>{
      const x = pad + i*stepX;
      const y = h - pad - ((v-min)/range)*(h-pad*2);
      return [x,y];
    });
    const linePath = coords.map((c,i)=> (i===0?'M':'L')+c[0].toFixed(1)+','+c[1].toFixed(1)).join(' ');
    const areaPath = linePath + ` L${coords[coords.length-1][0].toFixed(1)},${h-pad} L${coords[0][0].toFixed(1)},${h-pad} Z`;
    const dots = coords.map((c,i)=>`<circle class="chart-pt" data-val="${pts[i]}" cx="${c[0].toFixed(1)}" cy="${c[1].toFixed(1)}" r="9" fill="transparent" style="cursor:pointer"/>`).join('');
    const lastDot = coords[coords.length-1];

    $('#chartTotal').textContent = fmt(series.total);
    $('#chartDelta').textContent = series.delta;
    $('#chartDelta').className = series.up ? '' : 'down';

    $('#salesChart').innerHTML = `
      <defs>
        <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#1F3A34" stop-opacity="0.16"/>
          <stop offset="100%" stop-color="#1F3A34" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${areaPath}" fill="url(#chartFill)" stroke="none"/>
      <path d="${linePath}" fill="none" stroke="#1F3A34" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${lastDot[0].toFixed(1)}" cy="${lastDot[1].toFixed(1)}" r="4.5" fill="#B08D57" stroke="#F8F6F1" stroke-width="2"/>
      ${dots}
    `;
    const tip = $('#chartTooltip');
    $$('#salesChart .chart-pt').forEach(dot=>{
      dot.addEventListener('mousemove', e=>{
        const rect = $('#salesChart').getBoundingClientRect();
        const wrapRect = $('#chartWrap').getBoundingClientRect();
        tip.style.opacity = 1;
        tip.style.left = (rect.left - wrapRect.left + parseFloat(dot.getAttribute('cx')) * (rect.width/w)) + 'px';
        tip.style.top = (rect.top - wrapRect.top + parseFloat(dot.getAttribute('cy')) * (rect.height/h)) + 'px';
        tip.textContent = fmt(dot.dataset.val);
      });
      dot.addEventListener('mouseleave', ()=> tip.style.opacity = 0);
    });
  }

  /* ================= Dashboard: recent orders / best sellers / low stock ================= */
  function statusBadgeClass(status){
    return { 'נמסר':'success','נשלח':'info','בטיפול':'warning','ממתין לאישור':'neutral','בוטל':'danger' }[status] || 'neutral';
  }
  function payBadgeClass(pay){
    return { 'שולם':'success','ממתין לתשלום':'warning','נכשל':'danger' }[pay] || 'neutral';
  }

  function renderRecentOrders(){
    const rows = [...ORDERS].sort((a,b)=> b.date.localeCompare(a.date)).slice(0,6).map(o=>`
      <tr>
        <td><b class="cell-title">#${o.id}</b></td>
        <td>
          <div class="cell-main">
            <div class="avatar-sm">${initials(o.customer.name)}</div>
            <span>${o.customer.name}</span>
          </div>
        </td>
        <td class="text-faint">${fmtDate(o.date)}</td>
        <td class="num">${fmt(o.total)}</td>
        <td><span class="status-badge ${statusBadgeClass(o.status)}">${o.status}</span></td>
        <td class="cell-actions"><button class="icon-action" data-view-order="${o.id}" title="צפייה"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg></button></td>
      </tr>
    `).join('');
    $('#recentOrdersBody').innerHTML = rows;
    bindOrderViewButtons();
  }

  function renderBestSellers(){
    const top = [...PRODUCTS].sort((a,b)=>b.sold-a.sold).slice(0,5);
    $('#bestSellersBody').innerHTML = top.map(p=>`
      <tr>
        <td><div class="cell-main">${productImgHtml(p,34)}<span class="cell-title">${p.name}</span></div></td>
        <td class="text-faint">${p.cat}</td>
        <td class="num">${fmt(p.price)}</td>
        <td class="num">${p.sold}</td>
      </tr>
    `).join('');
  }

  function renderLowStock(){
    const low = PRODUCTS.filter(p=>p.stock<=p.threshold).sort((a,b)=>a.stock-b.stock);
    if(!low.length){ $('#lowStockList').innerHTML = emptyState('אין התראות מלאי','כל המוצרים במלאי תקין כרגע.'); return; }
    $('#lowStockList').innerHTML = low.slice(0,6).map(p=>`
      <div class="stock-row">
        ${productImgHtml(p,38)}
        <div class="stock-info"><b>${p.name}</b><span>מק"ט ${p.sku}</span></div>
        <span class="stock-badge ${p.stock===0?'critical':'low'}">${p.stock===0?'אזל מהמלאי':'נותרו '+p.stock}</span>
      </div>
    `).join('');
  }

  function emptyState(title, desc, iconSvg){
    return `<div class="empty-state">
      <div class="stamp-wrap"><svg viewBox="0 0 24 24">${iconSvg || '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3" stroke-linecap="round"/>'}</svg></div>
      <h4>${title}</h4><p>${desc}</p>
    </div>`;
  }

  /* ================= Products page ================= */
  let productView = 'table';
  function renderProducts(){
    const q = ($('#productSearch').value||'').trim().toLowerCase();
    const cat = $('#productCatFilter').value;
    const status = $('#productStatusFilter').value;
    let list = PRODUCTS.filter(p=>{
      if(q && !p.name.toLowerCase().includes(q) && !p.sku.toLowerCase().includes(q)) return false;
      if(cat && p.cat!==cat) return false;
      if(status && p.status!==status) return false;
      return true;
    });
    $('#productResultsCount').textContent = `${list.length} מוצרים`;

    if(!list.length){
      $('#productTableWrap').innerHTML = emptyState('לא נמצאו מוצרים','נסה לשנות את מונחי החיפוש או המסננים.');
      return;
    }

    if(productView==='table'){
      $('#productTableWrap').innerHTML = `
        <div class="table-scroll"><table class="data-table">
          <thead><tr><th>מוצר</th><th>קטגוריה</th><th>מחיר</th><th>מלאי</th><th>סטטוס</th><th></th></tr></thead>
          <tbody>${list.map(p=>productRow(p)).join('')}</tbody>
        </table></div>
        <div class="pagination"><span class="pg-info">מציג 1–${list.length} מתוך ${list.length}</span>
          <div class="pg-btns"><button class="pg-btn active">1</button></div>
        </div>`;
    } else {
      $('#productTableWrap').innerHTML = `<div class="product-grid">${list.map(p=>productCard(p)).join('')}</div>`;
    }
    bindProductRowActions();
  }
  function statusLabel(s){ return {active:'פעיל',draft:'טיוטה',out:'אזל מהמלאי'}[s] || s; }
  function statusCls(s){ return {active:'success',draft:'neutral',out:'danger'}[s] || 'neutral'; }
  function productRow(p){
    return `<tr>
      <td><div class="cell-main">${productImgHtml(p,40)}<div><div class="cell-title">${p.name}</div><div class="cell-sub">מק"ט ${p.sku}</div></div></div></td>
      <td class="text-faint">${p.cat}</td>
      <td class="num">${fmt(p.price)}</td>
      <td class="num">${p.stock<=p.threshold ? `<span style="color:var(--danger);font-weight:700">${p.stock}</span>` : p.stock}</td>
      <td><span class="status-badge ${statusCls(p.status)}">${statusLabel(p.status)}</span></td>
      <td class="cell-actions">
        <button class="icon-action" data-edit-product="${p.id}" title="עריכה"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 20h4L20 8l-4-4L4 16v4Z" stroke-linejoin="round"/></svg></button>
        <button class="icon-action danger" data-delete-product="${p.id}" title="מחיקה"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7"/></svg></button>
      </td>
    </tr>`;
  }
  function productCard(p){
    return `<div class="pgrid-card">
      ${productImgHtml(p,190).replace('class="thumb','class="thumb pgrid-thumb')}
      <div class="pgrid-body">
        <div class="pgrid-cat">${p.cat}</div>
        <div class="pgrid-name">${p.name}</div>
        <div class="pgrid-foot">
          <span class="pgrid-price">${fmt(p.price)}</span>
          <div class="cell-actions">
            <button class="icon-action" data-edit-product="${p.id}"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 20h4L20 8l-4-4L4 16v4Z" stroke-linejoin="round"/></svg></button>
            <button class="icon-action danger" data-delete-product="${p.id}"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7"/></svg></button>
          </div>
        </div>
      </div>
    </div>`;
  }
  function bindProductRowActions(){
    $$('[data-edit-product]').forEach(b=> b.addEventListener('click', ()=> openProductModal(b.dataset.editProduct)));
    $$('[data-delete-product]').forEach(b=> b.addEventListener('click', ()=>{
      const p = PRODUCTS.find(x=>x.id===b.dataset.deleteProduct);
      openConfirm({
        title:'מחיקת מוצר',
        desc:`${p.name}\n\nהפעולה תמחק את המוצר לצמיתות מ-MongoDB. לא ניתן לבטל פעולה זו.`,
        confirmLabel:'מחק מוצר',
        onConfirm: async ()=>{
          try{
            await BereshitData.deleteProduct(p.sharedId);
            const idx = PRODUCTS.indexOf(p);
            if(idx > -1) PRODUCTS.splice(idx, 1);
            renderKPIs(); renderProducts(); renderInventory(); renderCategories(); renderBestSellers(); renderLowStock();
            $('#lowStockBadge').textContent = PRODUCTS.filter(x=>x.stock<=x.threshold).length;
            toast('המוצר נמחק');
          }catch(err){
            toast('מחיקת המוצר נכשלה: ' + err.message);
          }
        }
      });
    }));
  }
  function initProductsPage(){
    refreshCategorySelects();
    $('#productSearch').addEventListener('input', renderProducts);
    $('#productCatFilter').addEventListener('change', renderProducts);
    $('#productStatusFilter').addEventListener('change', renderProducts);
    $$('.view-toggle button').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        $$('.view-toggle button').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        productView = btn.dataset.view;
        renderProducts();
      });
    });
    $('#addProductBtn').addEventListener('click', ()=> openProductModal(null));
  }

  /* ---- Product modal ---- */
  function catKeyForLabel(label){
    const c = CATEGORIES.find(x=>x.name===label);
    return c ? c.key : (CATEGORIES[0] ? CATEGORIES[0].key : '');
  }
  const PRODUCT_FIELD_IDS = ['pfName','pfSku','pfPrice','pfStock','pfThreshold'];

  function renderImagePreview(url, categoryLabel){
    const wrap = $('#pfImagePreview');
    if(url){
      wrap.innerHTML = `<div class="thumb"><img src="${escAttr(url)}" alt="" onerror="this.parentElement.innerHTML='<svg viewBox=\\'0 0 24 24\\'>${catIcon(categoryLabel).replace(/'/g,"\\'")}</svg>'"></div>`;
    } else {
      wrap.innerHTML = `<div class="thumb"><svg viewBox="0 0 24 24">${catIcon(categoryLabel)}</svg></div>`;
    }
  }

  let productModalToken = 0;

  function openProductModal(id){
    const p = id ? PRODUCTS.find(x=>x.id===id) : null;
    const myToken = ++productModalToken; // guards a stale async response landing after a newer modal open
    clearFieldErrors(PRODUCT_FIELD_IDS);

    $('#productModalTitle').textContent = p ? 'עריכת מוצר' : 'הוספת מוצר חדש';
    $('#productModalSub').textContent = p ? p.name : 'הוסף מוצר חדש לקטלוג בראשית יודאיקה';

    $('#pfName').value = p ? p.name : '';
    $('#pfSku').value = p ? p.sku : 'BJ-' + Math.floor(1000+Math.random()*9000);
    $('#pfCategory').innerHTML = categoryLabels().map(c=>`<option ${p&&p.cat===c?'selected':''}>${c}</option>`).join('');
    $('#pfStatus').value = p ? p.status : 'active';

    $('#pfPrice').value = p ? p.price : '';
    $('#pfOldPrice').value = (p && p.oldPrice!=null) ? p.oldPrice : '';
    $('#pfBadge').value = (p && p.badge) ? p.badge : '';

    $('#pfStock').value = p ? p.stock : '';
    $('#pfThreshold').value = p ? p.threshold : 5;

    $('#pfShort').value = '';
    $('#pfDesc').value = '';
    $('#pfMaterial').value = '';
    $('#pfDim').value = '';

    $('#pfImageUrl').value = p && p.image ? p.image : '';
    renderImagePreview(p ? p.image : null, $('#pfCategory').value);

    const firstTab = $('#productModal .tab-btn');
    if(firstTab) firstTab.click();
    openModal('#productModal');

    $('#pfImageUrl').oninput = ()=> renderImagePreview($('#pfImageUrl').value.trim(), $('#pfCategory').value);
    $('#pfCategory').onchange = ()=>{ if(!$('#pfImageUrl').value.trim()) renderImagePreview(null, $('#pfCategory').value); };
    $('#pfImageRemoveBtn').onclick = ()=>{ $('#pfImageUrl').value=''; renderImagePreview(null, $('#pfCategory').value); };

    // Assigned synchronously, before any await, so a save click is never
    // handled by a handler left over from a previous modal open.
    $('#saveProductBtn').onclick = async ()=>{
      clearFieldErrors(PRODUCT_FIELD_IDS);
      const name = $('#pfName').value.trim();
      const sku = $('#pfSku').value.trim();
      const price = Number($('#pfPrice').value);
      const stock = Number($('#pfStock').value);
      const threshold = Number($('#pfThreshold').value);
      const oldPriceRaw = $('#pfOldPrice').value.trim();
      const oldPrice = oldPriceRaw ? Number(oldPriceRaw) : null;

      let hasError = false;
      if(!name){ setFieldError('pfName','שם המוצר הוא שדה חובה'); hasError = true; }
      if(!sku){ setFieldError('pfSku','מק"ט הוא שדה חובה'); hasError = true; }
      else if(!/^[A-Za-z0-9-]{2,24}$/.test(sku)){ setFieldError('pfSku','מק"ט יכול להכיל אותיות אנגליות, ספרות ומקפים בלבד'); hasError = true; }
      if(!Number.isFinite(price) || price<0){ setFieldError('pfPrice','נא להזין מחיר תקין (0 ומעלה)'); hasError = true; }
      if(!Number.isInteger(stock) || stock<0){ setFieldError('pfStock','כמות במלאי חייבת להיות מספר שלם 0 ומעלה'); hasError = true; }
      if(!Number.isInteger(threshold) || threshold<0){ setFieldError('pfThreshold','סף מלאי נמוך חייב להיות מספר שלם 0 ומעלה'); hasError = true; }
      if(hasError){ toast('נא לתקן את השדות המסומנים'); return; }

      const catLabel = $('#pfCategory').value;
      const payload = {
        name, sku, price,
        oldPrice: (oldPriceRaw && Number.isFinite(oldPrice)) ? oldPrice : null,
        badge: $('#pfBadge').value || null,
        cat: catKeyForLabel(catLabel), catLabel,
        status: $('#pfStatus').value,
        stock, threshold,
        short: $('#pfShort').value.trim(),
        desc: $('#pfDesc').value.trim(),
        material: $('#pfMaterial').value.trim(),
        dim: $('#pfDim').value.trim(),
        image: $('#pfImageUrl').value.trim() || null,
      };

      try{
        await withBusy($('#saveProductBtn'), 'שומר...', async ()=>{
          if(p){
            const updated = await BereshitData.updateProduct(p.sharedId, payload);
            Object.assign(p, { name:updated.name, cat:updated.catLabel, catKey:updated.cat, price:updated.price, oldPrice:updated.oldPrice, badge:updated.badge, stock:updated.stock, threshold:updated.threshold, sku:updated.sku, status:updated.status, image:updated.image });
          } else {
            const created = await BereshitData.createProduct(payload);
            PRODUCTS.push({ id:String(created.id), sharedId:created.id, name:created.name, cat:created.catLabel, catKey:created.cat, price:created.price, oldPrice:created.oldPrice, badge:created.badge, stock:created.stock, threshold:created.threshold, sku:created.sku, status:created.status, sold:created.sold, image:created.image });
          }
        });
        closeModal('#productModal');
        renderKPIs(); renderProducts(); renderInventory(); renderCategories(); renderBestSellers(); renderLowStock();
        $('#lowStockBadge').textContent = PRODUCTS.filter(x=>x.stock<=x.threshold).length;
        toast(p ? 'המוצר עודכן בהצלחה' : 'המוצר נוסף בהצלחה');
      }catch(err){
        toast('שמירת המוצר נכשלה: ' + err.message);
      }
    };

    if(p){
      BereshitData.getProduct(p.sharedId).then(full=>{
        if(productModalToken !== myToken) return; // a newer modal open has since happened
        $('#pfShort').value = full.short || '';
        $('#pfDesc').value = full.desc || '';
        $('#pfMaterial').value = full.material || '';
        $('#pfDim').value = full.dim || '';
      }).catch(()=>{ /* keep the form usable even if this extra fetch fails */ });
    }
  }

  /* ================= Orders page ================= */
  const ORDER_STATUS_FLOW = ['ממתין לאישור','בטיפול','נשלח','נמסר'];
  const ORDER_CANCELLABLE_FROM = ['ממתין לאישור','בטיפול'];

  function renderOrders(){
    const q = ($('#orderSearch').value||'').trim().toLowerCase();
    const status = $('#orderStatusFilter').value;
    const pay = $('#orderPayFilter').value;
    let list = ORDERS.filter(o=>{
      if(q && !o.id.toLowerCase().includes(q) && !o.customer.name.toLowerCase().includes(q)) return false;
      if(status && o.status!==status) return false;
      if(pay && o.pay!==pay) return false;
      return true;
    });
    $('#orderResultsCount').textContent = `${list.length} הזמנות`;
    if(!list.length){
      $('#orderTableWrap').innerHTML = emptyState('לא נמצאו הזמנות','נסה לשנות את מונחי החיפוש או המסננים.');
      return;
    }
    $('#orderTableWrap').innerHTML = `
      <div class="table-scroll"><table class="data-table">
        <thead><tr><th>הזמנה</th><th>לקוח</th><th>תאריך</th><th>פריטים</th><th>סה"כ</th><th>תשלום</th><th>סטטוס</th><th></th></tr></thead>
        <tbody>${list.map(o=>`
          <tr>
            <td><b class="cell-title">#${o.id}</b></td>
            <td><div class="cell-main"><div class="avatar-sm">${initials(o.customer.name)}</div><span>${o.customer.name}</span></div></td>
            <td class="text-faint">${fmtDate(o.date)}</td>
            <td class="text-faint">${o.items.reduce((s,it)=>s+it.qty,0)} פריטים</td>
            <td class="num">${fmt(o.total)}</td>
            <td><span class="status-badge ${payBadgeClass(o.pay)}">${o.pay}</span></td>
            <td><span class="status-badge ${statusBadgeClass(o.status)}">${o.status}</span></td>
            <td class="cell-actions"><button class="btn btn-outline btn-sm" data-view-order="${o.id}">צפייה</button></td>
          </tr>
        `).join('')}</tbody>
      </table></div>
      <div class="pagination"><span class="pg-info">מציג 1–${list.length} מתוך ${list.length}</span>
        <div class="pg-btns"><button class="pg-btn active">1</button></div>
      </div>`;
    bindOrderViewButtons();
  }
  function bindOrderViewButtons(){
    $$('[data-view-order]').forEach(b=> b.addEventListener('click', ()=> openOrderModal(b.dataset.viewOrder)));
  }
  function initOrdersPage(){
    $('#orderSearch').addEventListener('input', renderOrders);
    $('#orderStatusFilter').addEventListener('change', renderOrders);
    $('#orderPayFilter').addEventListener('change', renderOrders);
  }

  /* ---- Order details modal ---- */
  function nextOrderStatusOptions(current){
    if(current==='בוטל' || current==='נמסר') return [current];
    const idx = ORDER_STATUS_FLOW.indexOf(current);
    const opts = [current];
    if(idx>-1 && idx<ORDER_STATUS_FLOW.length-1) opts.push(ORDER_STATUS_FLOW[idx+1]);
    return opts;
  }

  function afterOrderStatusChange(){
    renderOrders(); renderRecentOrders(); renderKPIs();
  }

  function openOrderModal(id){
    const o = ORDERS.find(x=>x.id===id);
    if(!o) return;
    $('#orderModalTitle').textContent = '#' + o.id;
    $('#orderModalSub').textContent = fmtDate(o.date) + ' · ' + o.items.reduce((s,it)=>s+it.qty,0) + ' פריטים';

    $('#omCustomer').innerHTML = `<b>${o.customer.name}</b><span>${o.customer.email}</span><span>${o.customer.phone}</span>`;
    $('#omShipping').innerHTML = `<b>${o.shipping.method}</b><span>${o.shipping.address}</span><span>${o.shipping.city}, ${o.shipping.zip}</span>`;
    $('#omPayment').innerHTML = `<b>${o.payment.method}</b><span>סטטוס: ${o.pay}</span><span>${fmtDate(o.payment.date)}</span>`;

    $('#omLines').innerHTML = o.items.map(it=>{
      const prod = PRODUCTS.find(x=>x.sharedId===it.productId);
      const img = prod ? productImgHtml(prod,44) : thumbHtml(it.cat,44);
      return `<div class="order-line">
        ${img}
        <div class="order-line-info"><b>${it.name}</b><span>${it.cat} · כמות ${it.qty}</span></div>
        <div class="order-line-total">${fmt(it.price*it.qty)}</div>
      </div>`;
    }).join('');

    const shippingCost = o.shipping.method==='שליח עד הבית' ? (STORE_INFO.shippingCost ?? 25) : 0;
    const freeThreshold = STORE_INFO.freeShippingThreshold;
    const effectiveShipping = (freeThreshold!=null && o.total>=freeThreshold) ? 0 : shippingCost;
    $('#omSummary').innerHTML = `
      <div class="summary-row"><span>סכום ביניים</span><span>${fmt(o.total)}</span></div>
      <div class="summary-row"><span>משלוח</span><span>${effectiveShipping?fmt(effectiveShipping):'ללא עלות'}</span></div>
      <div class="summary-row total"><span>סה"כ לתשלום</span><span>${fmt(o.total+effectiveShipping)}</span></div>
    `;

    const cancelled = o.status==='בוטל';
    const activeIdx = ORDER_STATUS_FLOW.indexOf(o.status);
    $('#omTimeline').innerHTML = (cancelled ? [
      {label:'ההזמנה בוצעה', done:true},
      {label:'ההזמנה בוטלה', done:true, danger:true},
    ] : ORDER_STATUS_FLOW.map((s,i)=>({label:s, done:i<=activeIdx}))
    ).map(s=>`
      <div class="timeline-item">
        <div class="timeline-dot ${s.done?'done':''}" style="${s.danger?'background:var(--danger);color:#fff':''}">
          <svg viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">${s.done ? '<path d="M5 13l4 4L19 7"/>' : '<circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>'}</svg>
        </div>
        <div class="timeline-text"><b>${s.label}</b><span>${fmtDate(o.date)}</span></div>
      </div>
    `).join('');

    $('#orderModalFootStatus').innerHTML = `<span class="status-badge ${statusBadgeClass(o.status)}">${o.status}</span>`;

    const opts = nextOrderStatusOptions(o.status);
    const isTerminal = opts.length<=1;
    $('#omStatusSelect').innerHTML = opts.map(s=>`<option value="${s}">${s}</option>`).join('');
    $('#omStatusSelect').disabled = isTerminal;
    $('#omUpdateStatusBtn').disabled = isTerminal;
    $('#omUpdateStatusBtn').style.display = isTerminal ? 'none' : '';
    $('#omStatusSelect').style.display = isTerminal ? 'none' : '';
    $('#omCancelBtn').style.display = ORDER_CANCELLABLE_FROM.includes(o.status) ? '' : 'none';

    $('#omUpdateStatusBtn').onclick = async ()=>{
      const newStatus = $('#omStatusSelect').value;
      try{
        await withBusy($('#omUpdateStatusBtn'), 'מעדכן...', async ()=>{
          const updated = await BereshitData.updateOrderStatus(o.id, newStatus);
          Object.assign(o, { status:updated.status });
        });
        openOrderModal(o.id);
        afterOrderStatusChange();
        toast('סטטוס ההזמנה עודכן');
      }catch(err){ toast('עדכון הסטטוס נכשל: ' + err.message); }
    };

    $('#omCancelBtn').onclick = ()=>{
      openConfirm({
        title:'ביטול הזמנה',
        desc:`לבטל את הזמנה #${o.id}?\nהפעולה תעדכן את סטטוס ההזמנה ל"בוטל" ולא ניתן לבטל אותה.`,
        confirmLabel:'בטל הזמנה',
        onConfirm: async ()=>{
          try{
            const updated = await BereshitData.updateOrderStatus(o.id, 'בוטל');
            Object.assign(o, { status:updated.status });
            closeModal('#orderModal');
            afterOrderStatusChange();
            toast('ההזמנה בוטלה');
          }catch(err){ toast('ביטול ההזמנה נכשל: ' + err.message); }
        }
      });
    };

    openModal('#orderModal');
  }

  /* ================= Customers page ================= */
  function renderCustomers(){
    const q = ($('#customerSearch').value||'').trim().toLowerCase();
    let list = CUSTOMERS.filter(c=> !q || c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q));
    $('#customerResultsCount').textContent = `${list.length} לקוחות`;
    if(!list.length){ $('#customerTableWrap').innerHTML = emptyState('לא נמצאו לקוחות','נסה מונח חיפוש אחר.'); return; }
    $('#customerTableWrap').innerHTML = `
      <div class="table-scroll"><table class="data-table">
        <thead><tr><th>לקוח</th><th>אימייל</th><th>טלפון</th><th>הזמנות</th><th>סה"כ הוצאה</th><th>תאריך הרשמה</th><th></th></tr></thead>
        <tbody>${list.map(c=>`
          <tr>
            <td><div class="cell-main"><div class="avatar-sm">${initials(c.name)}</div><span class="cell-title">${c.name}</span></div></td>
            <td class="text-faint">${c.email}</td>
            <td class="text-faint">${c.phone}</td>
            <td class="num">${c.orders}</td>
            <td class="num">${fmt(c.spent)}</td>
            <td class="text-faint">${fmtDate(c.joined)}</td>
            <td class="cell-actions"><button class="btn btn-outline btn-sm" data-view-customer="${c.id}">פרטים</button></td>
          </tr>
        `).join('')}</tbody>
      </table></div>
      <div class="pagination"><span class="pg-info">מציג 1–${list.length} מתוך ${list.length}</span><div class="pg-btns"><button class="pg-btn active">1</button></div></div>
    `;
    $$('[data-view-customer]').forEach(b=> b.addEventListener('click', ()=> openCustomerModal(b.dataset.viewCustomer)));
  }
  function initCustomersPage(){
    $('#customerSearch').addEventListener('input', renderCustomers);
  }

  function openCustomerModal(customerId){
    const c = CUSTOMERS.find(x=>x.id===customerId);
    if(!c) return;
    $('#customerModalTitle').textContent = c.name;
    $('#cmContact').innerHTML = `<b>${c.email}</b><span>${c.phone}</span><span>לקוח/ה מאז ${fmtDate(c.joined)}</span>`;
    $('#cmSummary').innerHTML = `<b>${c.orders} הזמנות</b><span>סה"כ הוצאה: ${fmt(c.spent)}</span>`;
    $('#cmOrdersBody').innerHTML = `<tr><td colspan="4" class="text-faint">טוען הזמנות...</td></tr>`;
    openModal('#customerModal');

    BereshitData.getOrders({ customerId: c.id }).then(orders=>{
      if(!orders.length){ $('#cmOrdersBody').innerHTML = `<tr><td colspan="4" class="text-faint">אין הזמנות עדיין</td></tr>`; return; }
      $('#cmOrdersBody').innerHTML = orders.map(o=>`
        <tr>
          <td><b class="cell-title">#${o.id}</b></td>
          <td class="text-faint">${fmtDate(o.date)}</td>
          <td class="num">${fmt(o.total)}</td>
          <td><span class="status-badge ${statusBadgeClass(o.status)}">${o.status}</span></td>
        </tr>
      `).join('');
    }).catch(()=>{
      $('#cmOrdersBody').innerHTML = `<tr><td colspan="4" class="text-faint">שגיאה בטעינת ההזמנות</td></tr>`;
    });
  }

  /* ================= Categories page ================= */
  function renderCategories(){
    if(!CATEGORIES.length){ $('#categoryGrid').closest('.panel').querySelector('.table-scroll').innerHTML = emptyState('אין קטגוריות','הוסף קטגוריה ראשונה כדי להתחיל.'); return; }
    $('#categoryGrid').innerHTML = CATEGORIES.map(c=>`
      <tr>
        <td><div class="cell-main">${thumbHtml(c.name,38)}<span class="cell-title">${c.name}</span></div></td>
        <td class="num">${c.count} מוצרים</td>
        <td><span class="status-badge ${c.status==='active'?'success':'neutral'}">${c.status==='active'?'פעיל':'לא פעיל'}</span></td>
        <td class="cell-actions">
          <button class="icon-action" data-edit-cat="${escAttr(c.key)}" title="עריכה"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 20h4L20 8l-4-4L4 16v4Z" stroke-linejoin="round"/></svg></button>
          <button class="icon-action danger" data-del-cat="${escAttr(c.key)}" title="מחיקה"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7"/></svg></button>
        </td>
      </tr>
    `).join('');
    $$('[data-del-cat]').forEach(b=> b.addEventListener('click', ()=>{
      const c = CATEGORIES.find(x=>x.key===b.dataset.delCat);
      if(c.count>0){
        openConfirm({
          title:'לא ניתן למחוק קטגוריה',
          desc:`"${c.name}" משויכת ל-${c.count} מוצרים.\nיש לשייך אותם לקטגוריה אחרת או למחוק אותם קודם.`,
          confirmLabel:'הבנתי', hideCancel:true,
        });
        return;
      }
      openConfirm({
        title:'מחיקת קטגוריה',
        desc:`למחוק את הקטגוריה "${c.name}"? הפעולה אינה הפיכה.`,
        confirmLabel:'מחק קטגוריה',
        onConfirm: async ()=>{
          try{
            await BereshitData.deleteCategory(c.key);
            const idx = CATEGORIES.indexOf(c);
            if(idx>-1) CATEGORIES.splice(idx,1);
            renderCategories(); refreshCategorySelects();
            toast('הקטגוריה נמחקה');
          }catch(err){ toast('מחיקת הקטגוריה נכשלה: ' + err.message); }
        }
      });
    }));
    $$('[data-edit-cat]').forEach(b=> b.addEventListener('click', ()=> openCategoryModal(b.dataset.editCat)));
  }
  function initCategoriesPage(){
    $('#addCategoryBtn').addEventListener('click', ()=> openCategoryModal(null));
  }

  const CATEGORY_FIELD_IDS = ['cfLabel','cfKey'];
  function openCategoryModal(key){
    const c = key ? CATEGORIES.find(x=>x.key===key) : null;
    clearFieldErrors(CATEGORY_FIELD_IDS);
    $('#categoryModalTitle').textContent = c ? 'עריכת קטגוריה' : 'הוספת קטגוריה';
    $('#cfLabel').value = c ? c.name : '';
    $('#cfKey').value = c ? c.key : '';
    $('#cfKey').disabled = !!c;
    $('#cfStatus').value = c ? c.status : 'active';
    openModal('#categoryModal');

    $('#saveCategoryBtn').onclick = async ()=>{
      clearFieldErrors(CATEGORY_FIELD_IDS);
      const label = $('#cfLabel').value.trim();
      const key2 = $('#cfKey').value.trim().toLowerCase();
      let hasError = false;
      if(!label){ setFieldError('cfLabel','שם הקטגוריה הוא שדה חובה'); hasError = true; }
      if(!c){
        if(!key2){ setFieldError('cfKey','מפתח טכני הוא שדה חובה'); hasError = true; }
        else if(!/^[a-z0-9_]{2,24}$/.test(key2)){ setFieldError('cfKey','מפתח יכול להכיל רק אותיות אנגליות קטנות, ספרות וקו תחתון'); hasError = true; }
        else if(CATEGORIES.some(x=>x.key===key2)){ setFieldError('cfKey','מפתח זה כבר קיים'); hasError = true; }
      }
      if(hasError) return;

      try{
        await withBusy($('#saveCategoryBtn'), 'שומר...', async ()=>{
          if(c){
            const updated = await BereshitData.updateCategory(c.key, { label, status:$('#cfStatus').value });
            Object.assign(c, { name:updated.label, status:updated.status });
          } else {
            const created = await BereshitData.createCategory({ key:key2, label, status:$('#cfStatus').value });
            CATEGORIES.push({ key:created.key, name:created.label, count:0, status:created.status, order:created.order });
          }
        });
        closeModal('#categoryModal');
        renderCategories(); refreshCategorySelects();
        toast(c ? 'הקטגוריה עודכנה' : 'הקטגוריה נוספה בהצלחה');
      }catch(err){
        toast('שמירת הקטגוריה נכשלה: ' + err.message);
      }
    };
  }

  /* ================= Inventory page ================= */
  function renderInventory(){
    const q = ($('#inventorySearch').value||'').trim().toLowerCase();
    const status = $('#inventoryStatusFilter').value;
    let list = PRODUCTS.filter(p=>{
      if(q && !p.name.toLowerCase().includes(q) && !p.sku.toLowerCase().includes(q)) return false;
      const st = p.stock===0?'out':(p.stock<=p.threshold?'low':'ok');
      if(status && status!==st) return false;
      return true;
    });
    $('#inventoryResultsCount').textContent = `${list.length} פריטים`;
    if(!list.length){ $('#inventoryTableWrap').innerHTML = emptyState('לא נמצאו פריטי מלאי','נסה לשנות את המסננים.'); return; }
    $('#inventoryTableWrap').innerHTML = `
      <div class="table-scroll"><table class="data-table">
        <thead><tr><th>מוצר</th><th>מק"ט</th><th>מלאי נוכחי</th><th>סף מלאי נמוך</th><th>סטטוס</th><th></th></tr></thead>
        <tbody>${list.map(p=>{
          const st = p.stock===0?'out':(p.stock<=p.threshold?'low':'ok');
          const stMap = {ok:['success','תקין'], low:['warning','נמוך'], out:['danger','אזל']};
          return `<tr>
            <td><div class="cell-main">${productImgHtml(p,36)}<span class="cell-title">${p.name}</span></div></td>
            <td class="text-faint">${p.sku}</td>
            <td class="num">${p.stock}</td>
            <td class="num text-faint">${p.threshold}</td>
            <td><span class="status-badge ${stMap[st][0]}">${stMap[st][1]}</span></td>
            <td class="cell-actions"><button class="btn btn-outline btn-sm" data-adjust="${p.id}">עדכון מלאי</button></td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>
    `;
    $$('[data-adjust]').forEach(b=> b.addEventListener('click', ()=> openInventoryModal(b.dataset.adjust)));
  }
  function initInventoryPage(){
    $('#inventorySearch').addEventListener('input', renderInventory);
    $('#inventoryStatusFilter').addEventListener('change', renderInventory);
  }

  const INVENTORY_FIELD_IDS = ['ivNewStock'];
  function openInventoryModal(id){
    const p = PRODUCTS.find(x=>x.id===id);
    if(!p) return;
    clearFieldErrors(INVENTORY_FIELD_IDS);
    $('#inventoryModalSub').textContent = `${p.name} · מק"ט ${p.sku}`;
    $('#ivCurrentStock').value = p.stock;
    $('#ivNewStock').value = p.stock;
    $('#ivReason').value = '';
    openModal('#inventoryModal');

    $('#saveInventoryBtn').onclick = async ()=>{
      clearFieldErrors(INVENTORY_FIELD_IDS);
      const newStock = Number($('#ivNewStock').value);
      if(!Number.isInteger(newStock) || newStock < 0){
        setFieldError('ivNewStock', 'יש להזין מספר שלם 0 ומעלה');
        return;
      }
      if(newStock === p.stock){
        closeModal('#inventoryModal');
        return; // no real change — nothing to save or log
      }
      try{
        await withBusy($('#saveInventoryBtn'), 'שומר...', async ()=>{
          const updated = await BereshitData.updateInventory(p.sharedId, newStock, $('#ivReason').value || undefined);
          p.stock = updated.stock;
          p.status = updated.status;
        });
        closeModal('#inventoryModal');
        renderKPIs(); renderLowStock(); renderInventory(); renderProducts(); renderCategories();
        $('#lowStockBadge').textContent = PRODUCTS.filter(x=>x.stock<=x.threshold).length;
        toast('המלאי עודכן ונשמר ב-MongoDB');
      }catch(err){
        toast('עדכון המלאי נכשל: ' + err.message);
      }
    };
  }

  /* ================= Promotions page ================= */
  function renderPromotions(){
    if(!PROMOTIONS.length){ $('#promoGrid').innerHTML = emptyState('אין מבצעים','צור מבצע ראשון כדי להתחיל.'); return; }
    const statusLbl = {active:'פעיל',scheduled:'מתוכנן',expired:'פג תוקף'};
    const statusCls2 = {active:'success',scheduled:'info',expired:'neutral'};
    const rank = s => s==='expired' ? 2 : (s==='scheduled' ? 1 : 0);
    const sorted = [...PROMOTIONS].sort((a,b)=> rank(a.status)-rank(b.status) || a.start.localeCompare(b.start));

    let html = '';
    let sawExpiredHeader = false;
    sorted.forEach(pr=>{
      if(pr.status==='expired' && !sawExpiredHeader){
        html += `<div style="grid-column:1/-1;font-size:11px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:0.06em;font-weight:700;margin-top:4px;padding-top:14px;border-top:1px solid var(--line);">מבצעים שפגו</div>`;
        sawExpiredHeader = true;
      }
      html += `<div class="promo-card ${pr.status}" data-edit-promo="${pr.id}" role="button" tabindex="0" style="cursor:pointer;">
        <div class="promo-top">
          <span class="promo-code">${pr.code}</span>
          <span class="status-badge ${statusCls2[pr.status]}">${statusLbl[pr.status]}</span>
        </div>
        <div class="promo-discount">${pr.discount>0 ? pr.discount+'% הנחה' : 'משלוח חינם'}</div>
        <div class="promo-name">${pr.name}</div>
        <div class="promo-dates"><span>${fmtDate(pr.start)}</span><span>עד ${fmtDate(pr.end)}</span></div>
      </div>`;
    });
    $('#promoGrid').innerHTML = html;
    $$('[data-edit-promo]').forEach(el=> el.addEventListener('click', ()=> openPromotionModal(el.dataset.editPromo)));
  }
  function initPromotionsPage(){
    $('#addPromotionBtn').addEventListener('click', ()=> openPromotionModal(null));
  }

  const PROMO_FIELD_IDS = ['promoName','promoCode','promoDiscount'];
  function openPromotionModal(id){
    const pr = id ? PROMOTIONS.find(x=>x.id===id) : null;
    clearFieldErrors(PROMO_FIELD_IDS);
    $('#promoDatesError').textContent = '';
    $('#promotionModalTitle').textContent = pr ? 'עריכת מבצע' : 'יצירת מבצע';
    $('#promoName').value = pr ? pr.name : '';
    $('#promoCode').value = pr ? pr.code : '';
    $('#promoDiscount').value = pr ? pr.discount : '';
    $('#promoStart').value = pr ? pr.start : '';
    $('#promoEnd').value = pr ? pr.end : '';
    $('#promoStatus').value = pr ? pr.status : 'scheduled';
    openModal('#promotionModal');

    $('#savePromotionBtn').onclick = async ()=>{
      clearFieldErrors(PROMO_FIELD_IDS);
      $('#promoDatesError').textContent = '';
      const name = $('#promoName').value.trim();
      const code = $('#promoCode').value.trim().toUpperCase();
      const discount = Number($('#promoDiscount').value);
      const start = $('#promoStart').value;
      const end = $('#promoEnd').value;

      let hasError = false;
      if(!name){ setFieldError('promoName','שם המבצע הוא שדה חובה'); hasError = true; }
      if(!code){ setFieldError('promoCode','קוד קופון הוא שדה חובה'); hasError = true; }
      if(!Number.isFinite(discount) || discount<0 || discount>100){ setFieldError('promoDiscount','אחוז הנחה חייב להיות בין 0 ל-100'); hasError = true; }
      if(!start || !end){ $('#promoDatesError').textContent = 'יש להזין תאריך התחלה וסיום'; hasError = true; }
      else if(start > end){ $('#promoDatesError').textContent = 'תאריך הסיום חייב להיות אחרי תאריך ההתחלה'; hasError = true; }
      if(hasError) return;

      const payload = { name, code, discount, start, end, status:$('#promoStatus').value };
      try{
        await withBusy($('#savePromotionBtn'), 'שומר...', async ()=>{
          if(pr){
            const updated = await BereshitData.updatePromotion(pr.id, payload);
            Object.assign(pr, updated);
          } else {
            const created = await BereshitData.createPromotion(payload);
            PROMOTIONS.push(created);
          }
        });
        closeModal('#promotionModal');
        renderPromotions();
        toast(pr ? 'המבצע עודכן בהצלחה' : 'המבצע נוצר בהצלחה');
      }catch(err){
        toast('שמירת המבצע נכשלה: ' + err.message);
      }
    };
  }

  /* ================= Settings page ================= */
  function initSettingsPage(){
    $$('.settings-nav button').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        $$('.settings-nav button').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        $$('#settingsPage .tab-panel').forEach(p=>p.classList.toggle('active', p.dataset.tab===btn.dataset.tab));
      });
    });

    /* --- Store info (real, GET/PUT /api/store-info) --- */
    $('#storeInfoName').value = STORE_INFO.name || '';
    $('#storeInfoEmail').value = STORE_INFO.email || '';
    $('#storeInfoPhone').value = STORE_INFO.phone || '';
    $('#storeInfoAddress').value = STORE_INFO.address || '';
    $('#storeInfoDesc').value = STORE_INFO.description || '';
    $('#saveStoreInfoBtn').addEventListener('click', async ()=>{
      const patch = {
        name: $('#storeInfoName').value.trim(),
        email: $('#storeInfoEmail').value.trim(),
        phone: $('#storeInfoPhone').value.trim(),
        address: $('#storeInfoAddress').value.trim(),
        description: $('#storeInfoDesc').value.trim(),
      };
      try{
        await withBusy($('#saveStoreInfoBtn'), 'שומר...', async ()=>{
          Object.assign(STORE_INFO, await BereshitData.updateStoreInfo(patch));
        });
        toast('פרטי החנות נשמרו ב-MongoDB');
      }catch(err){ toast('שמירת פרטי החנות נכשלה: ' + err.message); }
    });

    /* --- Shipping (real, part of store-info) --- */
    $('#shipCostInput').value = STORE_INFO.shippingCost ?? '';
    $('#shipFreeThresholdInput').value = STORE_INFO.freeShippingThreshold ?? '';
    $('#saveShippingBtn').addEventListener('click', async ()=>{
      const shippingCost = Number($('#shipCostInput').value);
      const freeShippingThreshold = Number($('#shipFreeThresholdInput').value);
      if(!Number.isFinite(shippingCost) || shippingCost<0 || !Number.isFinite(freeShippingThreshold) || freeShippingThreshold<0){
        toast('נא להזין ערכים מספריים תקינים (0 ומעלה)');
        return;
      }
      try{
        await withBusy($('#saveShippingBtn'), 'שומר...', async ()=>{
          Object.assign(STORE_INFO, await BereshitData.updateStoreInfo({ shippingCost, freeShippingThreshold }));
        });
        toast('הגדרות המשלוח נשמרו');
      }catch(err){ toast('שמירה נכשלה: ' + err.message); }
    });

    /* --- Payment methods (real, part of store-info) --- */
    const methods = STORE_INFO.paymentMethods || [];
    $('#payMethodCard').checked = methods.includes('credit_card');
    $('#payMethodPaypal').checked = methods.includes('paypal');
    $('#payMethodBit').checked = methods.includes('bit');
    $('#savePaymentBtn').addEventListener('click', async ()=>{
      const paymentMethods = [];
      if($('#payMethodCard').checked) paymentMethods.push('credit_card');
      if($('#payMethodPaypal').checked) paymentMethods.push('paypal');
      if($('#payMethodBit').checked) paymentMethods.push('bit');
      try{
        await withBusy($('#savePaymentBtn'), 'שומר...', async ()=>{
          Object.assign(STORE_INFO, await BereshitData.updateStoreInfo({ paymentMethods }));
        });
        toast('הגדרות התשלום נשמרו');
      }catch(err){ toast('שמירה נכשלה: ' + err.message); }
    });
  }

  /* ================= Modals (generic open/close) ================= */
  function openModal(sel){
    const el = $(sel);
    el.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeModal(sel){
    const el = $(sel);
    el.classList.remove('open');
    if(!$$('.modal-overlay.open').length) document.body.style.overflow = '';
  }
  function initModalCloses(){
    $$('.modal-overlay').forEach(overlay=>{
      overlay.addEventListener('click', e=>{ if(e.target===overlay) closeModal('#'+overlay.id); });
    });
    $$('[data-close-modal]').forEach(b=> b.addEventListener('click', ()=> closeModal('#'+b.dataset.closeModal)));
    document.addEventListener('keydown', e=>{
      if(e.key==='Escape'){ $$('.modal-overlay.open').forEach(o=> closeModal('#'+o.id)); }
    });
  }

  /* ---- Confirm dialog (generic, for destructive actions and quantity prompts) ---- */
  function openConfirm({title, desc, confirmLabel='אישור', hideCancel=false, onConfirm, input}){
    $('#confirmTitle').textContent = title;
    $('#confirmDesc').textContent = desc;
    $('#confirmOkBtn').textContent = confirmLabel;
    $('#confirmCancelBtn').style.display = hideCancel ? 'none' : '';
    $('#confirmOkBtn').className = 'btn ' + (hideCancel ? 'btn-primary' : 'btn-danger');

    const inputWrap = $('#confirmInputWrap');
    if(input){
      inputWrap.classList.remove('hidden');
      $('#confirmInputLabel').textContent = input.label;
      $('#confirmInputField').value = input.value;
      $('#confirmInputField').min = input.min ?? 0;
    } else {
      inputWrap.classList.add('hidden');
    }

    $('#confirmOkBtn').onclick = ()=>{
      const val = input ? Number($('#confirmInputField').value) : undefined;
      closeModal('#confirmModal');
      if(onConfirm) onConfirm(val);
    };
    openModal('#confirmModal');
  }

  /* ================= Tabs (Add Product modal) ================= */
  function initProductModalTabs(){
    $$('#productModal .tab-btn').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        $$('#productModal .tab-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        $$('#productModal .tab-panel').forEach(p=>p.classList.toggle('active', p.dataset.tab===btn.dataset.tab));
      });
    });
  }

  /* ================= Global search (topbar) ================= */
  function initTopbarSearch(){
    $('#globalSearch').addEventListener('keydown', e=>{
      if(e.key==='Enter' && e.target.value.trim()){
        navigateTo('products');
        $('#productSearch').value = e.target.value.trim();
        renderProducts();
        e.target.value='';
      }
    });
  }

  /* ================= Keyboard activation for role="button" elements ================= */
  function initKeyboardActivation(){
    document.addEventListener('keydown', e=>{
      if((e.key==='Enter' || e.key===' ') && e.target.matches('[role="button"]')){
        e.preventDefault();
        e.target.click();
      }
    });
  }

  /* ================= Init ================= */
  async function boot(){
    $('#brandLogoImg').src = BRAND_LOGO;
    $('#adminAvatarInitials').textContent = ADMIN_USER.initials;
    $('#topbarAvatarInitials').textContent = ADMIN_USER.initials;
    $('#sidebarAdminName').textContent = ADMIN_USER.name;
    $('#sidebarAdminRole').textContent = ADMIN_USER.role;
    $('#topbarAdminName').textContent = ADMIN_USER.name;
    $('#topbarAdminRole').textContent = ADMIN_USER.role;

    try{
      await loadAdminData();
    }catch(err){
      console.error('[Bereshit Admin] Failed to load data from the API:', err);
      toast('לא ניתן להתחבר לשרת ה-API. ודא שה-Flask server רץ ורענן את הדף.');
      return;
    }

    $('#lowStockBadge').textContent = PRODUCTS.filter(p=>p.stock<=p.threshold).length;

    initSidebarNav();
    initModalCloses();
    initKeyboardActivation();
    initChartControls();
    initProductsPage();
    initOrdersPage();
    initCustomersPage();
    initCategoriesPage();
    initInventoryPage();
    initPromotionsPage();
    initSettingsPage();
    initProductModalTabs();
    initTopbarSearch();

    renderKPIs();
    renderChart(currentPeriod);
    renderRecentOrders();
    renderBestSellers();
    renderLowStock();
    renderProducts();
    renderOrders();
    renderCustomers();
    renderCategories();
    renderInventory();
    renderPromotions();

    navigateTo('dashboard');
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
