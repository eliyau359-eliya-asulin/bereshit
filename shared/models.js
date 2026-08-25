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
 *
 * Presentation-only note: product photography is intentionally NOT part
 * of this model. Each app resolves its own images for a product id from
 * a local asset map (see USER_PRODUCT_IMAGES in index.html and the
 * icon-based placeholders in admin/js/data.js) — the same way a real
 * app would resolve an `imageUrl`/CDN key without inlining binary data
 * into the shared business-data layer.
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
 * @property {string} name
 * @property {string} cat
 * @property {number} price             Unit price at time of order.
 * @property {number} qty
 */

/**
 * @typedef {Object} Order
 * @property {string} id                e.g. "BJ-10234".
 * @property {string} customerId        References Customer.id.
 * @property {string} date              ISO date string (YYYY-MM-DD).
 * @property {OrderLineItem[]} items
 * @property {number} total
 * @property {('ממתין לאישור'|'בטיפול'|'נשלח'|'נמסר'|'בוטל')} status
 * @property {('שולם'|'ממתין לתשלום'|'נכשל')} pay
 * @property {{address:string, city:string, zip:string, method:string}} shipping
 * @property {{method:string, date:string}} payment
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
 */
