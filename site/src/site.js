/* Marks which download fits this device and draws the frog. No tracking, no network requests. */
(function () {
  var ua = navigator.userAgent || '';
  document.body.setAttribute('data-platform', /Android/i.test(ua) ? 'android' : /iPhone|iPad|iPod/i.test(ua) ? 'ios' : 'desktop');
  var A = window.TadpoleAssets, rows = A.stages[5], pal = A.palettes.green, parts = [];
  rows.forEach(function (row, y) { for (var x = 0; x < row.length; x++) if (row[x] !== '.') parts.push('<rect x="' + x + '" y="' + y + '" width="1" height="1" fill="' + pal[row[x]] + '"/>'); });
  document.getElementById('frog').innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="192" viewBox="0 0 ' + A.w + ' ' + A.h + '" shape-rendering="crispEdges" role="img" aria-label="A frog">' + parts.join('') + '</svg>';
})();
