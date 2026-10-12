/* Where entries live. In the browser (and the demo) they are kept in localStorage; inside the Android app the same calls go to the phone's own
 * database through the TadpoleNative bridge, which is also what the home-screen widget reads. */
(function (root) {
  'use strict';
  var KEY = 'tadpole.v1';

  function LocalStore() {
    var data = { entries: [], settings: {}, docs: [] };
    try { var raw = root.localStorage.getItem(KEY); if (raw) data = Object.assign(data, JSON.parse(raw)); } catch (e) { /* private mode or damaged: start empty */ }
    function save() { try { root.localStorage.setItem(KEY, JSON.stringify(data)); } catch (e) { /* storage full or blocked */ } }
    return {
      native: false,
      load: function () { return { entries: data.entries.slice(), settings: Object.assign({}, data.settings), docs: data.docs.slice() }; },
      put: function (e) { var i = data.entries.findIndex(function (x) { return x.id === e.id; }); if (i >= 0) data.entries[i] = e; else data.entries.push(e); save(); },
      set: function (k, v) { data.settings[k] = v; save(); },
      snapshot: function () {},
      deleteAll: function () { data = { entries: [], settings: {}, docs: [] }; save(); },
      saveFile: function (name, mime, text) {
        var a = root.document.createElement('a');
        a.href = root.URL.createObjectURL(new root.Blob([text], { type: mime })); a.download = name;
        root.document.body.appendChild(a); a.click(); a.remove();
        return true;
      },
      sync: null
    };
  }

  function NativeStore(n) {
    var ok = function (s) { try { return JSON.parse(s); } catch (e) { return null; } };
    return {
      native: true,
      load: function () { var d = ok(n.loadAll()) || {}; return { entries: d.entries || [], settings: d.settings || {}, docs: d.docs || [] }; },
      put: function (e) { n.putEntry(JSON.stringify(e)); },
      set: function (k, v) { n.setSetting(k, String(v)); },
      snapshot: function (s) { n.saveSnapshot(JSON.stringify(s)); },
      deleteAll: function () { n.deleteAll(); },
      saveFile: function (name, mime, text) { return !!n.saveFile(name, mime, text); },
      sync: {
        status: function () { return ok(n.syncStatus()) || {}; },
        now: function () { return n.syncNow(); },
        unpair: function () { n.unpair(); },
        pair: function (link) { return n.pair(link); }
      }
    };
  }

  root.TadpoleStore = { create: function () { return root.TadpoleNative ? NativeStore(root.TadpoleNative) : LocalStore(); } };
})(window);
