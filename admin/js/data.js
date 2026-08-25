/* ===================================================================
   Bereshit Judaica — Admin Dashboard
   Data adapter: shapes the shared data layer (shared/data-service.js)
   into the flat arrays admin.js renders. No data is hardcoded here —
   the canonical values live in shared/mock-data.js and are reached
   only through window.BereshitData, so both the admin dashboard and
   the customer site read the exact same product/category catalog.
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
const CAT_LIST = CAT_ICONS ? Object.keys(CAT_ICONS) : [];
function catIcon(cat){ return CAT_ICONS[cat] || CAT_ICONS['מתנות']; }

/* ---------- Products & categories (from the shared data layer) ---------- */
const SHARED_PRODUCTS = BereshitData.getProducts();
const SHARED_CATEGORIES = BereshitData.getCategories();

const PRODUCTS = SHARED_PRODUCTS.map(p => ({
  id: String(p.id),        // admin DOM dataset attributes are always strings
  sharedId: p.id,           // original id, for writing back through BereshitData
  name: p.name,
  cat: p.catLabel,
  price: p.price,
  stock: p.stock,
  threshold: p.threshold,
  sku: p.sku,
  status: p.status,
  sold: p.sold,
}));

const CATEGORIES = SHARED_CATEGORIES.map((c,i)=>({
  id:'C-'+(i+1),
  key: c.key,
  name: c.label,
  count: PRODUCTS.filter(p=>p.cat===c.label).length,
  status: c.status || 'active',
}));

/* ---------- Customers (from the shared data layer) ---------- */
const CUSTOMERS = BereshitData.getCustomers();

/* ---------- Orders (from the shared data layer) ---------- */
const ORDERS = BereshitData.getOrders().map(o => ({
  id: o.id,
  customer: o.customer,
  date: o.date,
  items: o.items.map(it => ({ name: it.name, cat: it.cat, price: it.price, qty: it.qty })),
  total: o.total,
  status: o.status,
  pay: o.pay,
  shipping: o.shipping,
  payment: o.payment,
}));

/* ---------- Promotions (from the shared data layer) ---------- */
const PROMOTIONS = BereshitData.getPromotions();

/* ---------- Store info (from the shared data layer) ---------- */
const STORE_INFO = BereshitData.getStoreInfo();

/* ---------- Sales chart series (mock, per period — not part of the shared model yet) ---------- */
const SALES_SERIES = {
  today: { total:4280, delta:'+6.2%', points:[120,180,90,260,310,220,410,380,520,460,610,540,720,690,470] },
  '7d': { total:28650, delta:'+11.4%', points:[3200,4100,3800,5200,4600,3900,3850] },
  '30d': { total:118400, delta:'+8.1%', points: [3400,3900,3100,4200,4600,3700,4100,3300,4800,5100,3900,4400,4700,3600,5200,4900,4100,3800,5300,5600,4200,4700,5100,4400,3900,5800,6100,5400,5900,6300] },
  year: { total:1284300, delta:'+15.7%', points:[82000,74000,91000,88000,95000,102000,98000,110000,105000,120000,116000,103300] },
};

/* ---------- Admin user (mock) ---------- */
const ADMIN_USER = { name:'ליאת אשכול', role:'מנהלת חנות', initials:'ל.א' };
