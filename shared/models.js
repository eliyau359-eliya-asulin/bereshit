/* ===================================================================
   Bereshit Judaica — Shared Data Models
   ===================================================================
   Plain JSDoc typedefs describing the shape of the business data that
   both the customer-facing site (/index.html) and the admin dashboard
   (/admin) read from the shared data layer (shared/data-service.js).

   This file has no runtime behavior — it is documentation only, kept
   close to the data it describes so it stays accurate, and it doubles
   as the reference shape for whoever wires up a real backend/API
   later (see the "// TODO: replace with real API call" markers in
   shared/data-service.js).

   Inventory is intentionally NOT a separate model: current stock and
   the low-stock threshold live on the Product itself (stock,
   threshold, status). A dedicated /inventory API endpoint later can
   still return objects shaped like { productId, stock, threshold },
   which is just a projection of these same Product fields.
   =================================================================== */

/**
 * @typedef {Object} Product
 * @property {number} id                Stable numeric id (matches order line items, favorites, cart entries).
 * @property {string} sku               Stock-keeping unit, admin-facing.
 * @property {string} cat               Category key (matches Category.key).
 * @property {string} catLabel          Category display label (Hebrew), denormalized for cheap rendering.
 * @property {string} name              Product display name.
 * @property {number} price             Current price, in ILS (₪).
 * @property {?number} oldPrice         Previous/strikethrough price, or null.
 * @property {?('new'|'sale')} badge    Merchandising badge shown on the storefront, or null.
 * @property {string} short             Short description (used on cards).
 * @property {string} desc              Full description (used on product detail).
 * @property {string} material          Material/finish description.
 * @property {string} dim               Dimensions description.
 * @property {number} stock             Units currently in stock.
 * @property {number} threshold         Stock level at/below which the product counts as "low stock".
 * @property {('active'|'draft'|'out')} status  Admin-facing lifecycle status.
 * @property {number} sold              Cumulative units sold (for "best sellers").
 * @property {?string} image            URL/path to a hosted product photo, or null.
 *
 * Presentation-only note: `image` is a URL string, never binary data —
 * MongoDB stores a reference, not the photo itself. The customer site's
 * original 17-product catalog still resolves its real photography from a
 * local asset map (see PRODUCT_IMAGES in index.html) since those photos
 * predate this field and aren't hosted anywhere with a URL yet; any new
 * or edited product uses `image` directly, with a placeholder icon shown
 * wherever it's null (see thumbHtml/productImgHtml in admin/js/admin.js).
 */

/**
 * @typedef {Object} Category
 * @property {string} key               Stable machine key (e.g. "kiddush").
 * @property {string} label             Hebrew display label.
 * @property {('active'|'inactive')} status  Admin-facing lifecycle status.
 * @property {number} order             Curated display order for the storefront's
 *                                       category navigation — MongoDB's default _id
 *                                       sort is alphabetical, not display order.
 */

/**
 * @typedef {Object} OrderLineItem
 * @property {number} productId
 * @property {string} name              Snapshot at order time — never re-read from the live product later.
 * @property {string} sku               Snapshot at order time.
 * @property {string} cat
 * @property {number} price             Unit price at time of order (snapshot, ignores later price changes).
 * @property {number} qty
 * @property {number} lineTotal         price * qty, computed server-side.
 */

/**
 * @typedef {Object} Order
 * @property {string} id                e.g. "BJ-10234".
 * @property {string} customerId        References Customer.id.
 * @property {string} date              ISO date string (YYYY-MM-DD).
 * @property {OrderLineItem[]} items
 * @property {number} total             Items subtotal (historical field name — does NOT include shipping).
 * @property {number} shippingCost      Shipping charged at order time, computed server-side from StoreInfo
 *                                       (shippingCost/freeShippingThreshold) — a snapshot, so it stays correct
 *                                       even if store settings change later.
 * @property {number} grandTotal        total + shippingCost.
 * @property {('ממתין לאישור'|'בטיפול'|'נשלח'|'נמסר'|'בוטל')} status  New orders always start at 'ממתין לאישור'.
 * @property {('שולם'|'ממתין לתשלום'|'נכשל')} pay     New orders always start 'ממתין לתשלום' — no payment
 *                                                     processing exists yet (Phase 1: real order pipeline only).
 * @property {{address:string, city:string, zip:string, method:string, notes:string}} shipping
 *           Contact/address snapshot at order time — a customer's address changing later must not
 *           change how an old order displays.
 * @property {{method:string, date:string}} payment
 */

/**
 * POST /api/orders request body (see BereshitData.createOrder):
 * @typedef {Object} CheckoutPayload
 * @property {{name:string, email:string, phone:string}} customer
 * @property {{method?:string, address:string, city:string, zip?:string, notes?:string}} shipping
 * @property {{productId:number, qty:number}[]} items   Only id+qty are trusted — price/name/etc
 *                                                       are always read fresh from MongoDB server-side.
 * @property {{method:string}} payment                  Recorded as-is; no processing happens in Phase 1.
 *
 * Response: { order: { id, customerId, subtotal, shipping, total, status } } — `shipping` here is the
 * numeric cost (not the address object above), and `total` is the grand total (subtotal + shipping).
 */

/**
 * @typedef {Object} Customer
 * @property {string} id                e.g. "CU-201".
 * @property {string} name
 * @property {string} email
 * @property {string} phone
 * @property {number} orders            Order count (denormalized for the admin table).
 * @property {number} spent             Lifetime spend, in ILS.
 * @property {string} joined            ISO date string.
 */

/**
 * @typedef {Object} Promotion
 * @property {string} id
 * @property {string} name
 * @property {string} code              Coupon code.
 * @property {number} discount          Percentage, 0 for non-percentage promos (e.g. free shipping).
 * @property {string} start             ISO date string.
 * @property {string} end               ISO date string.
 * @property {('active'|'scheduled'|'expired')} status
 */

/**
 * @typedef {Object} StoreInfo
 * @property {string} name
 * @property {string} email
 * @property {string} phone
 * @property {string} address
 * @property {string} currency
 * @property {string} description
 * @property {number} shippingCost              Standard shipping cost, in ILS.
 * @property {number} freeShippingThreshold     Order subtotal at/above which shipping is free.
 * @property {string[]} paymentMethods          Enabled payment method keys, e.g. ["credit_card","paypal"].
 */
