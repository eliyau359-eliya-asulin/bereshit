/* ===================================================================
   Bereshit Judaica — Shared Data Service
   ===================================================================
   The single abstraction both the customer site and the admin
   dashboard use to read/write shared business data. Neither UI talks
   to the network directly — everything goes through window.BereshitData,
   which now calls the real Flask API (backend/), which is the only
   thing that talks to MongoDB. There is no local/mock/localStorage
   fallback: if the API is unreachable, calls reject and the caller is
   expected to show that (see index.html / admin/js/admin.js).

   Set window.BERESHIT_API_BASE before this script loads to force a
   specific API location. Otherwise the default is environment-aware:
   - In production (deployed on Vercel), the API is served from the
     same origin under /api via vercel.json's rewrite, so a relative
     '/api' is correct and never bakes a hostname into the static files.
   - In local dev, the static frontend (e.g. `python -m http.server` on
     :8123) and the Flask API (:5000) run as two separate origins, so
     localhost/127.0.0.1 on any port other than 5000 talks to the Flask
     dev server explicitly.

   Cross-tab / live real-time sync (SSE, WebSockets) is not implemented
   yet — every method here just does one HTTP request and resolves with
   the result. That's the next stage, on top of this REST API.
   =================================================================== */
(function(global){
  'use strict';

  function defaultApiBase(){
    const { hostname, port, protocol } = global.location || {};
    const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';
    const isSeparateDevServer = isLocalHost && port && port !== '5000';
    return isSeparateDevServer ? `${protocol}//${hostname}:5000/api` : '/api';
  }

  const API_BASE = global.BERESHIT_API_BASE || defaultApiBase();

  /** Multipart upload — separate from request() because that helper always
   * sends JSON; a File/Blob body needs its own Content-Type (the browser
   * sets the multipart boundary automatically, so this must NOT set
   * Content-Type itself). */
  async function uploadFile(path, file){
    let res;
    try{
      const form = new FormData();
      form.append('file', file);
      res = await fetch(API_BASE + path, { method:'POST', credentials:'include', body: form });
    }catch(networkErr){
      throw new Error(`לא ניתן להתחבר לשרת ה-API (${API_BASE}). ודא שה-Flask server רץ.`);
    }
    let body = null;
    try{ body = await res.json(); }catch(parseErr){ /* noop */ }
    if(!res.ok){
      const err = new Error((body && body.error) || `שגיאת שרת (${res.status})`);
      err.status = res.status; err.code = body && body.code;
      throw err;
    }
    return body;
  }

  async function request(path, options){
    let res;
    try{
      res = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        // Sends/receives the session cookie (admin or customer). Required
        // for every authenticated call, harmless for public ones.
        credentials: 'include',
        ...options,
      });
    }catch(networkErr){
      throw new Error(`לא ניתן להתחבר לשרת ה-API (${API_BASE}). ודא שה-Flask server רץ.`);
    }

    let body = null;
    try{ body = await res.json(); }catch(parseErr){ /* empty/non-JSON body is fine for some responses */ }

    if(!res.ok){
      const message = (body && body.error) || `שגיאת שרת (${res.status})`;
      const err = new Error(message);
      err.status = res.status;
      err.code = body && body.code;
      throw err;
    }
    return body;
  }

  const BereshitData = {

    /* ---------------- Products ---------------- */
    async getProducts(filters){
      const qs = filters ? '?' + new URLSearchParams(
        Object.fromEntries(Object.entries(filters).filter(([,v]) => v))
      ).toString() : '';
      return request('/products' + qs);
    },
    getProduct(id){ return request(`/products/${id}`); },
    /** Looks up a product by barcode, falling back to SKU — used by the
     * admin barcode scanner and its manual-entry fallback. */
    lookupProductByCode(code){ return request(`/products/lookup?code=${encodeURIComponent(code)}`); },
    createProduct(data){ return request('/products', { method:'POST', body: JSON.stringify(data) }); },
    updateProduct(id, patch){ return request(`/products/${id}`, { method:'PUT', body: JSON.stringify(patch) }); },
    /** Convenience wrapper — the backend keeps `status` consistent with `stock` and
     * records a real inventory_log entry (reason optional; defaults server-side). */
    updateInventory(id, newStock, reason){ return this.updateProduct(id, { stock: newStock, reason }); },
    deleteProduct(id){ return request(`/products/${id}`, { method:'DELETE' }); },
    /** Validates, resizes/optimizes to WebP, and stores the file in external
     * object storage (see backend/images/). Resolves { url, thumbnailUrl, width, height }. */
    uploadProductImage(file){ return uploadFile('/images/upload', file); },
    /** Best-effort: deletes an image from storage unless another product
     * still references it. Safe to call fire-and-forget after a save. */
    deleteProductImage(url){ return request('/images', { method:'DELETE', body: JSON.stringify({ url }) }); },
    /** Paginated audit trail of every real stock change (admin adjustments; online-order
     * decrements are reflected in orders, not here). Admin-only. */
    getInventoryLog({ productId, page = 1, pageSize = 50 } = {}){
      const qs = new URLSearchParams({ page, pageSize, ...(productId ? { productId } : {}) }).toString();
      return request('/products/inventory-log?' + qs);
    },

    /* ---------------- Categories ---------------- */
    getCategories(){ return request('/categories'); },
    getCategory(key){ return request(`/categories/${key}`); },
    createCategory(data){ return request('/categories', { method:'POST', body: JSON.stringify(data) }); },
    updateCategory(key, patch){ return request(`/categories/${key}`, { method:'PUT', body: JSON.stringify(patch) }); },
    /** Rejects with a message naming the product count if the category is still in use. */
    deleteCategory(key){ return request(`/categories/${key}`, { method:'DELETE' }); },

    /* ---------------- Orders ---------------- */
    getOrders(filters){
      const qs = filters ? '?' + new URLSearchParams(
        Object.fromEntries(Object.entries(filters).filter(([,v]) => v))
      ).toString() : '';
      return request('/orders' + qs);
    },
    getOrder(id){ return request(`/orders/${id}`); },
    updateOrderStatus(id, status){ return request(`/orders/${id}`, { method:'PUT', body: JSON.stringify({ status }) }); },
    /** Real checkout: server validates stock, computes price/shipping, decrements inventory,
     * and creates the order — see backend/services/orders_service.py:create_order.
     * Resolves with { order: { id, customerId, subtotal, shipping, total, status } }. */
    createOrder(data){ return request('/orders', { method:'POST', body: JSON.stringify(data) }); },

    /* ---------------- Customers ---------------- */
    getCustomers(){ return request('/customers'); },

    /* ---------------- Promotions ---------------- */
    getPromotions(){ return request('/promotions'); },
    createPromotion(data){ return request('/promotions', { method:'POST', body: JSON.stringify(data) }); },
    updatePromotion(id, patch){ return request(`/promotions/${id}`, { method:'PUT', body: JSON.stringify(patch) }); },

    /* ---------------- Store info ---------------- */
    getStoreInfo(){ return request('/store-info'); },
    updateStoreInfo(patch){ return request('/store-info', { method:'PUT', body: JSON.stringify(patch) }); },

    /* ---------------- Product bulk import (Excel/CSV) ---------------- */
    /** Absolute URL for the "download template" link — needs to be absolute
     * (not a bare '/api/...' path) because local dev serves the static
     * admin site and the Flask API from two different ports. */
    importTemplateUrl(){ return API_BASE + '/products/import/template'; },
    /** Validates a file against the current catalog/categories WITHOUT
     * writing anything. Resolves { rows, summary }. */
    previewProductImport(file){ return uploadFile('/products/import/preview', file); },
    /** Writes only the rows the caller marks valid=true (re-validated
     * server-side regardless). Resolves { created, updated, skipped, errors }. */
    applyProductImport(rows){ return request('/products/import/apply', { method:'POST', body: JSON.stringify({ rows }) }); },

    /* ---------------- Admin auth ---------------- */
    adminLogin(email, password){ return request('/auth/admin/login', { method:'POST', body: JSON.stringify({ email, password }) }); },
    adminLogout(){ return request('/auth/admin/logout', { method:'POST' }); },
    adminMe(){ return request('/auth/admin/me'); },
    listAdminUsers(){ return request('/admin/users'); },
    createAdminUser(data){ return request('/admin/users', { method:'POST', body: JSON.stringify(data) }); },
    updateAdminUser(id, patch){ return request(`/admin/users/${id}`, { method:'PUT', body: JSON.stringify(patch) }); },

    /* ---------------- Customer cart (logged-in customers only; guest cart stays in localStorage) ---------------- */
    getCart(){ return request('/cart'); },
    saveCart(items){ return request('/cart', { method:'PUT', body: JSON.stringify({ items }) }); },

    /* ---------------- Customer auth ---------------- */
    customerRegister(data){ return request('/auth/customer/register', { method:'POST', body: JSON.stringify(data) }); },
    customerLogin(email, password){ return request('/auth/customer/login', { method:'POST', body: JSON.stringify({ email, password }) }); },
    customerLogout(){ return request('/auth/customer/logout', { method:'POST' }); },
    customerMe(){ return request('/auth/customer/me'); },
    updateCustomerMe(patch){ return request('/auth/customer/me', { method:'PUT', body: JSON.stringify(patch) }); },
  };

  global.BereshitData = BereshitData;

})(window);
