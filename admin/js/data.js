/* ===================================================================
   Bereshit Judaica — Admin Dashboard
   Mock data only. No backend / API / database connections.
   =================================================================== */

/* ---------- Category icon paths (24x24, stroke-based, matches brand) ---------- */
const CAT_ICONS = {
  'חנוכיות': '<path d="M12 3v6M6 9h12l-1 4H7L6 9Z" stroke-linejoin="round"/><path d="M8 13v6h8v-6"/><path d="M4 21h16"/>',
  'מזוזות': '<rect x="8" y="3" width="8" height="18" rx="2"/><path d="M12 8v6"/>',
  'כלי קידוש': '<path d="M8 4h8l-1 8a3 3 0 0 1-3 3 3 3 0 0 1-3-3L8 4Z" stroke-linejoin="round"/><path d="M12 15v4M8 20h8"/>',
  'כלי שבת': '<path d="M4 9h16l-1.5 9a2 2 0 0 1-2 1.7H7.5a2 2 0 0 1-2-1.7L4 9Z" stroke-linejoin="round"/><path d="M8 9V6a4 4 0 0 1 8 0v3"/>',
  'תכשיטים': '<circle cx="12" cy="9" r="4"/><path d="M9 12.5 6 21h12l-3-8.5"/>',
  'טליתות וכיפות': '<path d="M4 18c0-5 3.5-9 8-9s8 4 8 9" /><path d="M4 18h16M10 9V5M14 9V5"/>',
  'הבדלה': '<path d="M12 2v7M9 6l3 3 3-3" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 13h12l-1 8H7l-1-8Z" stroke-linejoin="round"/>',
  'מתנות': '<rect x="4" y="9" width="16" height="11" rx="1"/><path d="M4 9h16M12 9v11M12 9c-2-3-6-3-6 0s4 2 6 0Zm0 0c2-3 6-3 6 0s-4 2-6 0Z"/>',
};
const CAT_LIST = Object.keys(CAT_ICONS);
function catIcon(cat){ return CAT_ICONS[cat] || CAT_ICONS['מתנות']; }

/* ---------- Products ---------- */
const PRODUCTS = [
  { id:'P-1001', name:'חנוכיית כסף "ירושלים"', cat:'חנוכיות', price:890, stock:4, threshold:5, sku:'HAN-JLM-01', status:'active', sold:38 },
  { id:'P-1002', name:'חנוכיית פליז מעוטרת', cat:'חנוכיות', price:420, stock:12, threshold:5, sku:'HAN-BRS-02', status:'active', sold:22 },
  { id:'P-1003', name:'מזוזה מכסף "עלה זית"', cat:'מזוזות', price:265, stock:18, threshold:6, sku:'MEZ-OLV-03', status:'active', sold:64 },
  { id:'P-1004', name:'מזוזה מעץ זית עם פס כסף', cat:'מזוזות', price:145, stock:3, threshold:6, sku:'MEZ-WOD-04', status:'active', sold:51 },
  { id:'P-1005', name:'גביע קידוש כסף מסורתי', cat:'כלי קידוש', price:610, stock:9, threshold:4, sku:'KID-CUP-05', status:'active', sold:29 },
  { id:'P-1006', name:'סט קידוש כסף עם צלחת', cat:'כלי קידוש', price:980, stock:2, threshold:4, sku:'KID-SET-06', status:'active', sold:17 },
  { id:'P-1007', name:'סכין חלה עם ידית פנינה', cat:'כלי שבת', price:210, stock:15, threshold:5, sku:'CHL-KNF-07', status:'active', sold:45 },
  { id:'P-1008', name:'מגש חלה כסף חתוך', cat:'כלי שבת', price:540, stock:6, threshold:4, sku:'CHL-TRY-08', status:'active', sold:19 },
  { id:'P-1009', name:'זוג פמוטי שבת כסף "רימון"', cat:'כלי שבת', price:720, stock:1, threshold:4, sku:'CND-RIM-09', status:'active', sold:33 },
  { id:'P-1010', name:'שרשרת מגן דוד זהב 14K', cat:'תכשיטים', price:1250, stock:7, threshold:3, sku:'JWL-STD-10', status:'active', sold:12 },
  { id:'P-1011', name:'צמיד כסף חמסה', cat:'תכשיטים', price:320, stock:14, threshold:5, sku:'JWL-HMS-11', status:'active', sold:41 },
  { id:'P-1012', name:'טלית צמר איכותית פסים כחולים', cat:'טליתות וכיפות', price:380, stock:10, threshold:4, sku:'TAL-BLU-12', status:'active', sold:26 },
  { id:'P-1013', name:'כיפת סוואד רקומה', cat:'טליתות וכיפות', price:65, stock:40, threshold:10, sku:'KIP-EMB-13', status:'active', sold:88 },
  { id:'P-1014', name:'סט הבדלה כסף מלא', cat:'הבדלה', price:690, stock:5, threshold:4, sku:'HAV-SET-14', status:'active', sold:21 },
  { id:'P-1015', name:'קופסת בשמים מעוטרת', cat:'הבדלה', price:180, stock:0, threshold:5, sku:'HAV-BSM-15', status:'out', sold:9 },
  { id:'P-1016', name:'קערת פירות כסף מעוצבת', cat:'מתנות', price:450, stock:8, threshold:3, sku:'GFT-BWL-16', status:'active', sold:14 },
  { id:'P-1017', name:'תיק טלית רקום בשם אישי', cat:'מתנות', price:210, stock:11, threshold:4, sku:'GFT-BAG-17', status:'draft', sold:6 },
  { id:'P-1018', name:'ספר תורה מיניאטורי לקישוט', cat:'מתנות', price:340, stock:3, threshold:3, sku:'GFT-TOR-18', status:'active', sold:8 },
  { id:'P-1019', name:'חנוכיית זכוכית וכסף מודרנית', cat:'חנוכיות', price:560, stock:6, threshold:5, sku:'HAN-MOD-19', status:'active', sold:15 },
  { id:'P-1020', name:'מזוזה זעירה לרכב', cat:'מזוזות', price:95, stock:22, threshold:8, sku:'MEZ-CAR-20', status:'active', sold:37 },
];

const CATEGORIES = CAT_LIST.map((name,i)=>({
  id:'C-'+(i+1),
  name,
  count: PRODUCTS.filter(p=>p.cat===name).length,
  status: 'active',
}));

/* ---------- Customers ---------- */
const CUSTOMERS = [
  { id:'CU-201', name:'נועה כהן', email:'noa.cohen@example.com', phone:'050-1234567', orders:6, spent:3420, joined:'2024-11-03' },
  { id:'CU-202', name:'איתמר לוי', email:'itamar.levi@example.com', phone:'052-2345678', orders:3, spent:1180, joined:'2025-01-17' },
  { id:'CU-203', name:'שירה מזרחי', email:'shira.mizrahi@example.com', phone:'054-3456789', orders:9, spent:5640, joined:'2024-06-22' },
  { id:'CU-204', name:'דניאל אברהם', email:'daniel.avraham@example.com', phone:'053-4567890', orders:1, spent:420, joined:'2025-07-02' },
  { id:'CU-205', name:'מיכל בן דוד', email:'michal.bendavid@example.com', phone:'050-5678901', orders:4, spent:2260, joined:'2025-02-11' },
  { id:'CU-206', name:'יוסף פרץ', email:'yosef.peretz@example.com', phone:'058-6789012', orders:12, spent:8930, joined:'2023-12-05' },
  { id:'CU-207', name:'טליה גבאי', email:'talia.gabay@example.com', phone:'052-7890123', orders:2, spent:790, joined:'2025-05-19' },
  { id:'CU-208', name:'רועי שרון', email:'roi.sharon@example.com', phone:'054-8901234', orders:7, spent:4110, joined:'2024-09-14' },
  { id:'CU-209', name:'אביגיל נחום', email:'avigail.nachum@example.com', phone:'050-9012345', orders:5, spent:2890, joined:'2024-08-27' },
  { id:'CU-210', name:'עמית רוזן', email:'amit.rozen@example.com', phone:'053-0123456', orders:2, spent:640, joined:'2025-06-30' },
  { id:'CU-211', name:'הדר אשכנזי', email:'hadar.ashkenazi@example.com', phone:'058-1122334', orders:8, spent:5320, joined:'2024-04-10' },
  { id:'CU-212', name:'ליאור שמעוני', email:'lior.shimoni@example.com', phone:'052-2233445', orders:1, spent:265, joined:'2025-08-01' },
];

/* ---------- Orders ---------- */
function pick(arr,i){ return arr[i % arr.length]; }
const ORDER_STATUSES = ['ממתין לאישור','בטיפול','נשלח','נמסר','בוטל'];
const PAY_STATUSES = ['שולם','ממתין לתשלום','נכשל'];

const ORDERS = Array.from({length:16}).map((_,i)=>{
  const cust = pick(CUSTOMERS,i*3+1);
  const itemsCount = 1 + (i % 3);
  const items = Array.from({length:itemsCount}).map((_,k)=>{
    const p = pick(PRODUCTS,(i*2+k*5+3));
    const qty = 1 + ((i+k) % 2);
    return { name:p.name, cat:p.cat, price:p.price, qty, img:p.cat };
  });
  const total = items.reduce((s,it)=>s+it.price*it.qty,0);
  const status = pick(ORDER_STATUSES, i);
  const pay = status==='בוטל' ? 'נכשל' : pick(PAY_STATUSES, i+1);
  const day = 24 - i;
  return {
    id:'BJ-'+(10234+i),
    customer:cust,
    date:`2026-08-${String(Math.max(1,day)).padStart(2,'0')}`,
    items,
    total,
    status,
    pay,
    shipping:{ address:'רחוב הרצל 14, תל אביב', city:'תל אביב-יפו', zip:'6423806', method: i%3===0 ? 'שליח עד הבית' : 'איסוף עצמי מהחנות' },
    payment:{ method: i%4===0 ? 'PayPal' : 'כרטיס אשראי •••• '+(4000+i), date:`2026-08-${String(Math.max(1,day)).padStart(2,'0')}` },
  };
});

/* ---------- Promotions ---------- */
const PROMOTIONS = [
  { id:'PR-01', name:'מבצע ראש השנה', code:'ROSHHASHANA25', discount:25, start:'2026-08-20', end:'2026-09-10', status:'active' },
  { id:'PR-02', name:'הנחת לקוחות חדשים', code:'WELCOME10', discount:10, start:'2026-01-01', end:'2026-12-31', status:'active' },
  { id:'PR-03', name:'מבצע חנוכה', code:'CHANUKAH26', discount:20, start:'2026-11-25', end:'2026-12-20', status:'scheduled' },
  { id:'PR-04', name:'משלוח חינם מעל 500 ₪', code:'FREESHIP500', discount:0, start:'2026-06-01', end:'2026-12-31', status:'active' },
  { id:'PR-05', name:'מבצע קיץ', code:'SUMMER26', discount:15, start:'2026-06-01', end:'2026-08-15', status:'expired' },
  { id:'PR-06', name:'מבצע יום האהבה', code:'LOVE26', discount:18, start:'2027-02-05', end:'2027-02-15', status:'scheduled' },
];

/* ---------- Sales chart series (mock, per period) ---------- */
const SALES_SERIES = {
  today: { total:4280, delta:'+6.2%', points:[120,180,90,260,310,220,410,380,520,460,610,540,720,690,in_range()] },
  '7d': { total:28650, delta:'+11.4%', points:[3200,4100,3800,5200,4600,3900,3850] },
  '30d': { total:118400, delta:'+8.1%', points: gen30() },
  year: { total:1284300, delta:'+15.7%', points:[82000,74000,91000,88000,95000,102000,98000,110000,105000,120000,116000,103300] },
};
function in_range(){ return 470; }
function gen30(){
  const base=[3400,3900,3100,4200,4600,3700,4100,3300,4800,5100,3900,4400,4700,3600,5200,4900,4100,3800,5300,5600,4200,4700,5100,4400,3900,5800,6100,5400,5900,6300];
  return base;
}

/* ---------- Admin user (mock) ---------- */
const ADMIN_USER = { name:'ליאת אשכול', role:'מנהלת חנות', initials:'ל.א' };
