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

  async function request(path, options){
    let res;
    try{
      res = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
    }catch(networkErr){
      throw new Error(`לא ניתן להתחבר לשרת ה-API (${API_BASE}). ודא שה-Flask server רץ.`);
    }

    let body = null;
    try{ body = await res.json(); }catch(parseErr){ /* empty/non-JSON body is fine for some responses */ }

    if(!res.ok){
      const message = (body && body.error) || `שגיאת שרת (${res.status})`;
      throw new Error(message);
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
    createProduct(data){ return request('/products', { method:'POST', body: JSON.stringify(data) }); },
    updateProduct(id, patch){ return request(`/products/${id}`, { method:'PUT', body: JSON.stringify(patch) }); },
    /** Convenience wrapper — the backend keeps `status` consistent with `stock`. */
    updateInventory(id, newStock){ return this.updateProduct(id, { stock: newStock }); },
    deleteProduct(id){ return request(`/products/${id}`, { method:'DELETE' }); },

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

    /* ---------------- Customers ---------------- */
    getCustomers(){ return request('/customers'); },

    /* ---------------- Promotions ---------------- */
    getPromotions(){ return request('/promotions'); },
    createPromotion(data){ return request('/promotions', { method:'POST', body: JSON.stringify(data) }); },
    updatePromotion(id, patch){ return request(`/promotions/${id}`, { method:'PUT', body: JSON.stringify(patch) }); },

    /* ---------------- Store info ---------------- */
    getStoreInfo(){ return request('/store-info'); },
    updateStoreInfo(patch){ return request('/store-info', { method:'PUT', body: JSON.stringify(patch) }); },
  };

  global.BereshitData = BereshitData;

})(window);
