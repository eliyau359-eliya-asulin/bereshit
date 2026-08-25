/* ===================================================================
   Bereshit Judaica — Admin Dashboard (visual prototype)
   Vanilla JS. No backend / API / database. Mock data from data.js.
   =================================================================== */
(function(){
  'use strict';

  const $ = (sel,ctx=document)=>ctx.querySelector(sel);
  const $$ = (sel,ctx=document)=>Array.from(ctx.querySelectorAll(sel));
  const fmt = n => '₪' + Number(n).toLocaleString('he-IL');
  const fmtDate = d => { const dt=new Date(d); return dt.toLocaleDateString('he-IL',{day:'numeric',month:'short',year:'numeric'}); };
  const initials = name => name.trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('');

  /* ---------------- Toast ---------------- */
  let toastTimer;
  function toast(msg){
    const el = $('#toast');
    $('#toastText').textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(()=>el.classList.remove('show'), 2600);
  }

  /* ---------------- Thumb (placeholder image) ---------------- */
  function thumbHtml(cat, size){
    const gold = ['תכשיטים','הבדלה'].includes(cat);
    return `<div class="thumb${gold?' gold':''}" style="width:${size}px;height:${size}px"><svg viewBox="0 0 24 24">${catIcon(cat)}</svg></div>`;
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

  /* ================= Topbar dropdown ================= */
  function initDropdown(){
    const btn = $('#profileBtn'), menu = $('#profileMenu');
    btn.addEventListener('click', e=>{
      e.stopPropagation();
      menu.classList.toggle('open');
    });
    document.addEventListener('click', ()=> menu.classList.remove('open'));
    $('#logoutMenuItem').addEventListener('click', ()=>{
      menu.classList.remove('open');
      toast('התנתקות היא פעולה מושבתת בדמו החזותי');
    });
    $('#sidebarLogout').addEventListener('click', ()=>{
      toast('התנתקות היא פעולה מושבתת בדמו החזותי');
    });
  }

  /* ================= KPIs ================= */
  function renderKPIs(){
    const totalSales = ORDERS.reduce((s,o)=>s + (o.status!=='בוטל'?o.total:0),0);
    const lowStock = PRODUCTS.filter(p=>p.stock>0 && p.stock<=p.threshold).length;
    const kpis = [
      { label:'סה"כ מכירות', value:fmt(totalSales), trend:'+12.4%', up:true, icon:iconRevenue(), cls:'' },
      { label:'הזמנות', value:ORDERS.length, trend:'+4.8%', up:true, icon:iconOrders(), cls:'gold' },
      { label:'מוצרים', value:PRODUCTS.length, trend:'+2 החודש', up:true, icon:iconProducts(), cls:'' },
      { label:'לקוחות', value:CUSTOMERS.length, trend:'+3 החודש', up:true, icon:iconCustomers(), cls:'gold' },
      { label:'מלאי נמוך', value:lowStock, trend:'דורש טיפול', up:false, icon:iconAlert(), cls:'danger' },
    ];
    $('#kpiGrid').innerHTML = kpis.map(k=>`
      <div class="kpi-card">
        <div class="kpi-top">
          <div class="kpi-icon ${k.cls}"><svg class="icon" viewBox="0 0 24 24">${k.icon}</svg></div>
          <div class="kpi-trend ${k.up?'up':'down'}">${k.up?'▲':'●'} ${k.trend}</div>
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

  /* ================= Sales chart ================= */
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
    const series = SALES_SERIES[period];
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
    const rows = ORDERS.slice(0,6).map(o=>`
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
  }

  function renderBestSellers(){
    const top = [...PRODUCTS].sort((a,b)=>b.sold-a.sold).slice(0,5);
    $('#bestSellersBody').innerHTML = top.map(p=>`
      <tr>
        <td><div class="cell-main">${thumbHtml(p.cat,34)}<span class="cell-title">${p.name}</span></div></td>
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
        ${thumbHtml(p.cat,38)}
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
      <td><div class="cell-main">${thumbHtml(p.cat,40)}<div><div class="cell-title">${p.name}</div><div class="cell-sub">מק"ט ${p.sku}</div></div></div></td>
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
      ${thumbHtml(p.cat,190).replace('class="thumb','class="thumb pgrid-thumb')}
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
            renderKPIs(); renderProducts(); renderInventory(); renderCategories();
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
    $('#productCatFilter').innerHTML = `<option value="">כל הקטגוריות</option>` + CAT_LIST.map(c=>`<option value="${c}">${c}</option>`).join('');
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
    return c ? c.key : CATEGORIES[0].key;
  }

  let productModalToken = 0;

  function openProductModal(id){
    const p = id ? PRODUCTS.find(x=>x.id===id) : null;
    const myToken = ++productModalToken; // guards against a stale async response landing after a newer modal open
    $('#productModalTitle').textContent = p ? 'עריכת מוצר' : 'הוספת מוצר חדש';
    $('#productModalSub').textContent = p ? p.name : 'הוסף מוצר חדש לקטלוג בראשית יודאיקה';
    $('#pfName').value = p ? p.name : '';
    $('#pfDesc').value = '';
    $('#pfPrice').value = p ? p.price : '';
    $('#pfCategory').innerHTML = CAT_LIST.map(c=>`<option ${p&&p.cat===c?'selected':''}>${c}</option>`).join('');
    $('#pfSku').value = p ? p.sku : 'BJ-' + Math.floor(1000+Math.random()*9000);
    $('#pfStock').value = p ? p.stock : '';
    $('#pfThreshold').value = p ? p.threshold : 5;
    $('#pfStatus').value = p ? p.status : 'active';
    $('#productUploadThumbs').innerHTML = p ? thumbHtml(p.cat,56) : '';
    openModal('#productModal');

    // Assigned synchronously, before any await, so a save click is never
    // handled by a handler left over from a previous modal open.
    $('#saveProductBtn').onclick = async ()=>{
      const catLabel = $('#pfCategory').value;
      const payload = {
        name: $('#pfName').value.trim(),
        desc: $('#pfDesc').value.trim(),
        price: Number($('#pfPrice').value),
        cat: catKeyForLabel(catLabel),
        catLabel,
        sku: $('#pfSku').value.trim(),
        stock: Number($('#pfStock').value),
        threshold: Number($('#pfThreshold').value),
        status: $('#pfStatus').value,
      };
      try{
        if(p){
          const updated = await BereshitData.updateProduct(p.sharedId, payload);
          Object.assign(p, { name:updated.name, cat:updated.catLabel, price:updated.price, stock:updated.stock, threshold:updated.threshold, sku:updated.sku, status:updated.status });
        } else {
          const created = await BereshitData.createProduct(payload);
          PRODUCTS.push({ id:String(created.id), sharedId:created.id, name:created.name, cat:created.catLabel, price:created.price, stock:created.stock, threshold:created.threshold, sku:created.sku, status:created.status, sold:created.sold });
        }
        closeModal('#productModal');
        renderKPIs(); renderProducts(); renderInventory(); renderCategories(); renderBestSellers();
        $('#lowStockBadge').textContent = PRODUCTS.filter(x=>x.stock<=x.threshold).length;
        toast(p ? 'המוצר עודכן בהצלחה' : 'המוצר נוסף בהצלחה');
      }catch(err){
        toast('שמירת המוצר נכשלה: ' + err.message);
      }
    };

    if(p){
      BereshitData.getProduct(p.sharedId).then(full=>{
        if(productModalToken === myToken) $('#pfDesc').value = full.desc || '';
      }).catch(()=>{ /* keep the form usable even if this extra fetch fails */ });
    }
  }

  /* ================= Orders page ================= */
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
  function openOrderModal(id){
    const o = ORDERS.find(x=>x.id===id);
    if(!o) return;
    $('#orderModalTitle').textContent = '#' + o.id;
    $('#orderModalSub').textContent = fmtDate(o.date) + ' · ' + o.items.reduce((s,it)=>s+it.qty,0) + ' פריטים';

    $('#omCustomer').innerHTML = `<b>${o.customer.name}</b><span>${o.customer.email}</span><span>${o.customer.phone}</span>`;
    $('#omShipping').innerHTML = `<b>${o.shipping.method}</b><span>${o.shipping.address}</span><span>${o.shipping.city}, ${o.shipping.zip}</span>`;
    $('#omPayment').innerHTML = `<b>${o.payment.method}</b><span>סטטוס: ${o.pay}</span><span>${fmtDate(o.payment.date)}</span>`;

    $('#omLines').innerHTML = o.items.map(it=>`
      <div class="order-line">
        ${thumbHtml(it.cat,44)}
        <div class="order-line-info"><b>${it.name}</b><span>${it.cat} · כמות ${it.qty}</span></div>
        <div class="order-line-total">${fmt(it.price*it.qty)}</div>
      </div>
    `).join('');

    const shippingCost = o.shipping.method==='שליח עד הבית' ? 25 : 0;
    $('#omSummary').innerHTML = `
      <div class="summary-row"><span>סכום ביניים</span><span>${fmt(o.total)}</span></div>
      <div class="summary-row"><span>משלוח</span><span>${shippingCost?fmt(shippingCost):'ללא עלות'}</span></div>
      <div class="summary-row total"><span>סה"כ לתשלום</span><span>${fmt(o.total+shippingCost)}</span></div>
    `;

    const steps = ['ממתין לאישור','בטיפול','נשלח','נמסר'];
    const cancelled = o.status==='בוטל';
    const activeIdx = steps.indexOf(o.status);
    $('#omTimeline').innerHTML = (cancelled ? [
      {label:'ההזמנה בוצעה', done:true},
      {label:'ההזמנה בוטלה', done:true, danger:true},
    ] : steps.map((s,i)=>({label:s, done:i<=activeIdx}))
    ).map(s=>`
      <div class="timeline-item">
        <div class="timeline-dot ${s.done?'done':''}" style="${s.danger?'background:var(--danger);color:#fff':''}">
          <svg viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">${s.done ? '<path d="M5 13l4 4L19 7"/>' : '<circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>'}</svg>
        </div>
        <div class="timeline-text"><b>${s.label}</b><span>${fmtDate(o.date)}</span></div>
      </div>
    `).join('');

    $('#orderModalFootStatus').innerHTML = `<span class="status-badge ${statusBadgeClass(o.status)}">${o.status}</span>`;
    openModal('#orderModal', true);
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
    $$('[data-view-customer]').forEach(b=> b.addEventListener('click', ()=>{
      const c = CUSTOMERS.find(x=>x.id===b.dataset.viewCustomer);
      openConfirm({
        title:c.name,
        desc:`${c.email} · ${c.phone}\n${c.orders} הזמנות · סה"כ הוצאה ${fmt(c.spent)}\nלקוח/ה מאז ${fmtDate(c.joined)}`,
        confirmLabel:'סגור', hideCancel:true, icon:'user'
      });
    }));
  }
  function initCustomersPage(){
    $('#customerSearch').addEventListener('input', renderCustomers);
  }

  /* ================= Categories page ================= */
  function renderCategories(){
    $('#categoryGrid').innerHTML = CATEGORIES.map(c=>`
      <tr>
        <td><div class="cell-main">${thumbHtml(c.name,38)}<span class="cell-title">${c.name}</span></div></td>
        <td class="num">${c.count} מוצרים</td>
        <td><span class="status-badge success">פעיל</span></td>
        <td class="cell-actions">
          <button class="icon-action" data-edit-cat="${c.id}"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 20h4L20 8l-4-4L4 16v4Z" stroke-linejoin="round"/></svg></button>
          <button class="icon-action danger" data-del-cat="${c.id}"><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7"/></svg></button>
        </td>
      </tr>
    `).join('');
    $$('[data-del-cat]').forEach(b=> b.addEventListener('click', ()=> openConfirm({
      title:'מחיקת קטגוריה', desc:'מוצרים המשויכים לקטגוריה זו יישארו בקטלוג ללא שיוך קטגוריה.',
      confirmLabel:'מחק קטגוריה', onConfirm:()=> toast('הקטגוריה נמחקה (הדגמה חזותית בלבד)')
    })));
    $$('[data-edit-cat]').forEach(b=> b.addEventListener('click', ()=> toast('עריכת קטגוריה (הדגמה חזותית בלבד)')));
  }
  function initCategoriesPage(){
    $('#addCategoryBtn').addEventListener('click', ()=> toast('הוספת קטגוריה (הדגמה חזותית בלבד)'));
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
            <td><div class="cell-main">${thumbHtml(p.cat,36)}<span class="cell-title">${p.name}</span></div></td>
            <td class="text-faint">${p.sku}</td>
            <td class="num">${p.stock}</td>
            <td class="num text-faint">${p.threshold}</td>
            <td><span class="status-badge ${stMap[st][0]}">${stMap[st][1]}</span></td>
            <td class="cell-actions"><button class="btn btn-outline btn-sm" data-adjust="${p.id}">עדכן מלאי</button></td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>
    `;
    $$('[data-adjust]').forEach(b=> b.addEventListener('click', ()=>{
      const p = PRODUCTS.find(x=>x.id===b.dataset.adjust);
      const restockQty = 10;
      const newStock = p.stock + restockQty;
      openConfirm({
        title:'עדכון מלאי',
        desc:`${p.name}\nהוספת ${restockQty} יחידות למלאי: ${p.stock} ← ${newStock}.\n\nהעדכון יישמר בשכבת הנתונים המשותפת (BereshitData) ויהיה זמין גם לאתר הלקוחות בטעינה הבאה.`,
        confirmLabel:'עדכן מלאי',
        onConfirm: async ()=>{
          try{
            const updated = await BereshitData.updateInventory(p.sharedId, newStock);
            p.stock = updated.stock;
            p.status = updated.status;
            renderKPIs();
            renderLowStock();
            renderInventory();
            renderProducts();
            $('#lowStockBadge').textContent = PRODUCTS.filter(x=>x.stock<=x.threshold).length;
            toast('המלאי עודכן ונשמר ב-MongoDB');
          }catch(err){
            toast('עדכון המלאי נכשל: ' + err.message);
          }
        }
      });
    }));
  }
  function initInventoryPage(){
    $('#inventorySearch').addEventListener('input', renderInventory);
    $('#inventoryStatusFilter').addEventListener('change', renderInventory);
  }

  /* ================= Promotions page ================= */
  function renderPromotions(){
    const statusLbl = {active:'פעיל',scheduled:'מתוכנן',expired:'פג תוקף'};
    const statusCls2 = {active:'success',scheduled:'info',expired:'neutral'};
    $('#promoGrid').innerHTML = PROMOTIONS.map(pr=>`
      <div class="promo-card ${pr.status}">
        <div class="promo-top">
          <span class="promo-code">${pr.code}</span>
          <span class="status-badge ${statusCls2[pr.status]}">${statusLbl[pr.status]}</span>
        </div>
        <div class="promo-discount">${pr.discount>0 ? pr.discount+'% הנחה' : 'משלוח חינם'}</div>
        <div class="promo-name">${pr.name}</div>
        <div class="promo-dates"><span>${fmtDate(pr.start)}</span><span>עד ${fmtDate(pr.end)}</span></div>
      </div>
    `).join('');
  }
  function initPromotionsPage(){
    $('#addPromotionBtn').addEventListener('click', ()=> toast('יצירת מבצע חדש (הדגמה חזותית בלבד)'));
  }

  /* ================= Content page ================= */
  function initContentPage(){
    $$('#contentPage [data-content-action]').forEach(b=> b.addEventListener('click', ()=> toast('ניהול תוכן יחובר בהמשך הפיתוח')));
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
    $$('#settingsPage .btn-primary').forEach(b=>{
      if(b.id==='saveStoreInfoBtn') return;
      b.addEventListener('click', ()=> toast('ההגדרות נשמרו (הדגמה חזותית בלבד)'));
    });

    $('#storeInfoName').value = STORE_INFO.name;
    $('#storeInfoEmail').value = STORE_INFO.email;
    $('#storeInfoPhone').value = STORE_INFO.phone;
    $('#storeInfoAddress').value = STORE_INFO.address;
    $('#storeInfoDesc').value = STORE_INFO.description;

    $('#saveStoreInfoBtn').addEventListener('click', async ()=>{
      const patch = {
        name: $('#storeInfoName').value.trim(),
        email: $('#storeInfoEmail').value.trim(),
        phone: $('#storeInfoPhone').value.trim(),
        address: $('#storeInfoAddress').value.trim(),
        description: $('#storeInfoDesc').value.trim(),
      };
      try{
        const updated = await BereshitData.updateStoreInfo(patch);
        Object.assign(STORE_INFO, updated);
        toast('פרטי החנות נשמרו ב-MongoDB');
      }catch(err){
        toast('שמירת פרטי החנות נכשלה: ' + err.message);
      }
    });
  }

  /* ================= Modals (generic open/close) ================= */
  function openModal(sel, focusFirst){
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

  /* ---- Confirm dialog (generic, for destructive actions) ---- */
  function openConfirm({title, desc, confirmLabel='אישור', hideCancel=false, onConfirm}){
    $('#confirmTitle').textContent = title;
    $('#confirmDesc').textContent = desc;
    $('#confirmOkBtn').textContent = confirmLabel;
    $('#confirmCancelBtn').style.display = hideCancel ? 'none' : '';
    $('#confirmOkBtn').className = 'btn ' + (hideCancel ? 'btn-primary' : 'btn-danger');
    $('#confirmOkBtn').onclick = ()=>{ closeModal('#confirmModal'); if(onConfirm) onConfirm(); };
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
    initDropdown();
    initModalCloses();
    initKeyboardActivation();
    initChartControls();
    initProductsPage();
    initOrdersPage();
    initCustomersPage();
    initCategoriesPage();
    initInventoryPage();
    initPromotionsPage();
    initContentPage();
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
