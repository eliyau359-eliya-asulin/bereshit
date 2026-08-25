/* ===================================================================
   Bereshit Judaica — Shared Data Service
   ===================================================================
   The single abstraction both the customer site and the admin
   dashboard use to read/write shared business data. Neither UI talks
   to shared/mock-data.js directly, and neither hardcodes its own copy
   of products/orders/etc — everything goes through window.BereshitData.

   Today this is backed by an in-memory store seeded from mock data
   and persisted to localStorage (so an admin edit survives a reload
   and is visible to a freshly-loaded page — a stand-in for "the data
   came from a server"). Every read method below is marked with where
   a real API call would replace it; swapping the body of this file
   for `fetch('/api/...')` calls is the only change a real backend
   integration should require — no page should need to change.

   Cross-tab / live real-time sync (BroadcastChannel, SSE, WebSockets,
   the `storage` event) is deliberately NOT wired up yet — only the
   subscribe/emit plumbing is in place so it can be added later
   without changing how pages read data.
   =================================================================== */
(function(global){
  'use strict';

  const STORAGE_KEY = 'bereshit.sharedData.v1';

  function clone(value){
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  function loadPersisted(){
    try{
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    }catch(err){
      console.warn('[BereshitData] localStorage unavailable, using in-memory mock data only', err);
      return null;
    }
  }

  function persist(state){
    try{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }catch(err){
      console.warn('[BereshitData] failed to persist shared data', err);
    }
  }

  // Seed from the bundled mock catalog, then layer any previously
  // persisted admin edits on top (so the demo "remembers" changes).
  const seed = clone(global.BereshitMockData);
  let state = loadPersisted() || seed;
  // Guard against a stale/partial shape left over from an older version.
  ['PRODUCTS','CATEGORIES','CUSTOMERS','ORDERS','PROMOTIONS','STORE_INFO'].forEach(key=>{
    if(!state[key]) state[key] = seed[key];
  });

  const listeners = {};
  function emit(event, payload){
    (listeners[event] || []).forEach(fn=>{
      try{ fn(payload); }catch(err){ console.error('[BereshitData] subscriber threw', err); }
    });
  }

  function findProduct(id){
    return state.PRODUCTS.find(p => String(p.id) === String(id));
  }
  function findOrder(id){
    return state.ORDERS.find(o => String(o.id) === String(id));
  }

  const BereshitData = {

    /* ---------------- Products ---------------- */
    // TODO: replace with `await fetch('/api/products').then(r=>r.json())`
    getProducts(){ return clone(state.PRODUCTS); },
    getProduct(id){ const p = findProduct(id); return p ? clone(p) : null; },
    /** Partial update; returns the updated product, or null if not found. */
    updateProduct(id, patch){
      const p = findProduct(id);
      if(!p) return null;
      Object.assign(p, patch);
      persist(state);
      emit('products:changed', clone(state.PRODUCTS));
      emit('product:updated', clone(p));
      return clone(p);
    },
    /** Convenience wrapper: sets stock and keeps status consistent with it. */
    updateInventory(id, newStock){
      const p = findProduct(id);
      if(!p) return null;
      const status = newStock <= 0 ? 'out' : (p.status === 'draft' ? 'draft' : 'active');
      return this.updateProduct(id, { stock: Math.max(0, newStock), status });
    },

    /* ---------------- Categories ---------------- */
    // TODO: replace with `await fetch('/api/categories').then(r=>r.json())`
    getCategories(){ return clone(state.CATEGORIES); },

    /* ---------------- Orders ---------------- */
    // TODO: replace with `await fetch('/api/orders').then(r=>r.json())`
    getOrders(){ return clone(state.ORDERS); },
    getOrder(id){ const o = findOrder(id); return o ? clone(o) : null; },
    updateOrderStatus(id, status){
      const o = findOrder(id);
      if(!o) return null;
      o.status = status;
      persist(state);
      emit('orders:changed', clone(state.ORDERS));
      return clone(o);
    },

    /* ---------------- Customers ---------------- */
    // TODO: replace with `await fetch('/api/customers').then(r=>r.json())`
    getCustomers(){ return clone(state.CUSTOMERS); },

    /* ---------------- Promotions ---------------- */
    // TODO: replace with `await fetch('/api/promotions').then(r=>r.json())`
    getPromotions(){ return clone(state.PROMOTIONS); },

    /* ---------------- Store info ---------------- */
    // TODO: replace with `await fetch('/api/store-info').then(r=>r.json())`
    getStoreInfo(){ return clone(state.STORE_INFO); },
    updateStoreInfo(patch){
      Object.assign(state.STORE_INFO, patch);
      persist(state);
      emit('store:changed', clone(state.STORE_INFO));
      return clone(state.STORE_INFO);
    },

    /* ---------------- Pub/sub ----------------
       Not wired to any cross-tab transport yet (see file header).
       A future real-time layer (WebSocket/SSE/BroadcastChannel) would
       just call `emit(...)` here when a server push arrives, and every
       existing subscriber keeps working unchanged. */
    subscribe(event, fn){
      (listeners[event] = listeners[event] || []).push(fn);
      return function unsubscribe(){
        listeners[event] = (listeners[event] || []).filter(f => f !== fn);
      };
    },

    /** Dev/demo utility: discard persisted overrides and restore the seed catalog. */
    resetToDefaults(){
      state = clone(seed);
      persist(state);
      emit('products:changed', clone(state.PRODUCTS));
      emit('orders:changed', clone(state.ORDERS));
      emit('store:changed', clone(state.STORE_INFO));
    },
  };

  global.BereshitData = BereshitData;

})(window);
