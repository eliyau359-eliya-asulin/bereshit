/* ===================================================================
   Bereshit Judaica — Admin Dashboard
   Data adapter: shapes the shared data layer (shared/data-service.js,
   backed by the Flask API + MongoDB) into the flat arrays admin.js
   renders. No business data is hardcoded here — everything is loaded
   from the API via loadAdminData(), called once from admin.js's boot().
   =================================================================== */

/* ---------- Category icon paths (24x24, stroke-based, matches brand) ---------- */
const CAT_ICONS = {
  'גביעי קידוש': '<path d="M8 4h8l-1 8a3 3 0 0 1-3 3 3 3 0 0 1-3-3L8 4Z" stroke-linejoin="round"/><path d="M12 15v4M8 20h8"/>',
  'פמוטים': '<path d="M12 3v5M9 8h6l1 4H8l1-4Z" stroke-linejoin="round"/><path d="M7 12h10l-1.2 8a1.5 1.5 0 0 1-1.5 1.3H9.7A1.5 1.5 0 0 1 8.2 20L7 12Z" stroke-linejoin="round"/>',
  'חנוכיות': '<path d="M12 3v6M6 9h12l-1 4H7L6 9Z" stroke-linejoin="round"/><path d="M8 13v6h8v-6"/><path d="M4 21h16"/>',
  'מוצרי שבת': '<path d="M4 9h16l-1.5 9a2 2 0 0 1-2 1.7H7.5a2 2 0 0 1-2-1.7L4 9Z" stroke-linejoin="round"/><path d="M8 9V6a4 4 0 0 1 8 0v3"/>',
  'הבדלה': '<path d="M12 2v7M9 6l3 3 3-3" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 13h12l-1 8H7l-1-8Z" stroke-linejoin="round"/>',
  'מתנות': '<rect x="4" y="9" width="16" height="11" rx="1"/><path d="M4 9h16M12 9v11M12 9c-2-3-6-3-6 0s4 2 6 0Zm0 0c2-3 6-3 6 0s-4 2-6 0Z"/>',
  'כלי כסף': '<ellipse cx="12" cy="12" rx="8" ry="4.5"/><path d="M4 12v3c0 2.5 3.6 4.5 8 4.5s8-2 8-4.5v-3"/>',
};
function catIcon(cat){ return CAT_ICONS[cat] || CAT_ICONS['מתנות']; }

/* ---------- Data arrays, populated by loadAdminData() before boot() renders ---------- */
const PRODUCTS = [];
const CATEGORIES = [];
const CUSTOMERS = [];
const ORDERS = [];
const PROMOTIONS = [];
const STORE_INFO = {};

async function loadAdminData(){
  const [sharedProducts, sharedCategories, customers, orders, promotions, storeInfo] = await Promise.all([
    BereshitData.getProducts(),
    BereshitData.getCategories(),
    BereshitData.getCustomers(),
    BereshitData.getOrders(),
    BereshitData.getPromotions(),
    BereshitData.getStoreInfo(),
  ]);

  PRODUCTS.push(...sharedProducts.map(p => ({
    id: String(p.id),        // admin DOM dataset attributes are always strings
    sharedId: p.id,           // original id, for writing back through BereshitData
    name: p.name,
    cat: p.catLabel,
    catKey: p.cat,
    price: p.price,
    oldPrice: p.oldPrice,
    badge: p.badge,
    stock: p.stock,
    threshold: p.threshold,
    sku: p.sku,
    status: p.status,
    sold: p.sold,
    image: p.image || null,
    thumbnail: p.thumbnail || null,
  })));

  CATEGORIES.push(...sharedCategories.map(c=>({
    key: c.key,
    name: c.label,
    count: PRODUCTS.filter(p=>p.catKey===c.key).length,
    status: c.status || 'active',
    order: c.order,
  })));

  CUSTOMERS.push(...customers);

  ORDERS.push(...orders.map(o => ({
    id: o.id,
    customerId: o.customerId,
    customer: o.customer,
    date: o.date,
    items: o.items.map(it => ({ productId: it.productId, name: it.name, cat: it.cat, price: it.price, qty: it.qty })),
    total: o.total,
    status: o.status,
    pay: o.pay,
    shipping: o.shipping,
    payment: o.payment,
  })));

  PROMOTIONS.push(...promotions);

  Object.assign(STORE_INFO, storeInfo);
}

/* ---------- Real sales chart + KPI trends, computed from ORDERS ----------
   No fabricated numbers: every total, bucket, and % delta below is derived
   from the orders actually loaded from the API. Cancelled orders never
   count toward revenue. A period with no orders yet honestly shows ₪0
   rather than inventing activity. */
const DAY_MS = 86400000;

function dateOnly(d){ const c = new Date(d); c.setHours(0,0,0,0); return c; }
function parseOrderDate(s){ return new Date(s + 'T00:00:00'); }

function revenueBetween(start, end){ // [start, end)
  return ORDERS.reduce((sum,o)=>{
    if(o.status==='בוטל') return sum;
    const d = parseOrderDate(o.date);
    return (d>=start && d<end) ? sum + o.total : sum;
  }, 0);
}
function countBetween(start, end){
  return ORDERS.reduce((n,o)=>{
    if(o.status==='בוטל') return n;
    const d = parseOrderDate(o.date);
    return (d>=start && d<end) ? n+1 : n;
  }, 0);
}

function formatDelta(current, previous){
  if(previous > 0){
    const pct = ((current-previous)/previous)*100;
    return { text:(pct>=0?'+':'')+pct.toFixed(1)+'%', up: pct>=0 };
  }
  if(current > 0) return { text:'חדש', up:true };
  return { text:'אין שינוי', up:true };
}

function computeSalesSeries(period){
  const today = dateOnly(new Date());
  let points, total, prevTotal;

  if(period==='today'){
    total = revenueBetween(today, new Date(today.getTime()+DAY_MS));
    prevTotal = revenueBetween(new Date(today.getTime()-DAY_MS), today);
    points = [total, total];
  } else if(period==='7d' || period==='30d'){
    const days = period==='7d' ? 7 : 30;
    points = [];
    for(let i=days-1;i>=0;i--){
      const start = new Date(today.getTime()-i*DAY_MS);
      points.push(revenueBetween(start, new Date(start.getTime()+DAY_MS)));
    }
    total = points.reduce((a,b)=>a+b,0);
    const prevStart = new Date(today.getTime()-2*days*DAY_MS);
    const prevEnd = new Date(today.getTime()-days*DAY_MS);
    prevTotal = revenueBetween(prevStart, prevEnd);
  } else { // 'year': last 12 calendar months
    points = [];
    for(let i=11;i>=0;i--){
      const start = new Date(today.getFullYear(), today.getMonth()-i, 1);
      const end = new Date(today.getFullYear(), today.getMonth()-i+1, 1);
      points.push(revenueBetween(start, end));
    }
    total = points.reduce((a,b)=>a+b,0);
    const prevStart = new Date(today.getFullYear()-1, today.getMonth()+1, 1);
    const prevEnd = new Date(today.getFullYear(), today.getMonth()+1, 1);
    prevTotal = revenueBetween(prevStart, prevEnd);
  }

  const delta = formatDelta(total, prevTotal);
  return { total, points, delta: delta.text, up: delta.up };
}

/** 30-day-over-30-day revenue trend, used for the dashboard's "total sales" KPI. */
function computeSalesTrend(){
  const today = dateOnly(new Date());
  const cur = revenueBetween(new Date(today.getTime()-30*DAY_MS), new Date(today.getTime()+DAY_MS));
  const prev = revenueBetween(new Date(today.getTime()-60*DAY_MS), new Date(today.getTime()-30*DAY_MS));
  return formatDelta(cur, prev);
}
/** 30-day-over-30-day order-count trend, used for the "orders" KPI. */
function computeOrdersTrend(){
  const today = dateOnly(new Date());
  const cur = countBetween(new Date(today.getTime()-30*DAY_MS), new Date(today.getTime()+DAY_MS));
  const prev = countBetween(new Date(today.getTime()-60*DAY_MS), new Date(today.getTime()-30*DAY_MS));
  return formatDelta(cur, prev);
}
/** Real count of customers whose registration date falls in the current calendar month. */
function computeNewCustomersThisMonth(){
  const now = new Date();
  return CUSTOMERS.filter(c=>{
    const d = new Date(c.joined);
    return d.getFullYear()===now.getFullYear() && d.getMonth()===now.getMonth();
  }).length;
}

/* ---------- Current admin (real session, set by boot() after login) ---------- */
const ADMIN_USER = { id:null, name:'', role:'', roleLabel:'', initials:'' };
const ADMIN_USERS = [];

const ROLE_LABELS_HE = {
  super_admin: 'מנהל-על',
  admin: 'מנהל',
  inventory_manager: 'מנהל מלאי',
  orders_manager: 'מנהל הזמנות',
  content_manager: 'מנהל תוכן',
};

function initialsOf(name){
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if(!parts.length) return '?';
  return parts.slice(0,2).map(p=>p[0]).join('').toUpperCase();
}

function setCurrentAdmin(admin){
  ADMIN_USER.id = admin.id;
  ADMIN_USER.name = admin.name;
  ADMIN_USER.role = admin.role;
  ADMIN_USER.roleLabel = admin.roleLabel || admin.role;
  ADMIN_USER.initials = initialsOf(admin.name);
}

async function loadAdminUsersList(){
  ADMIN_USERS.length = 0;
  try{
    const list = await BereshitData.listAdminUsers();
    ADMIN_USERS.push(...list);
  }catch(err){
    // Non-super-admin roles get a 403 here — the Users tab simply stays
    // empty for them rather than throwing, since it's a secondary panel.
  }
}
