/* A small, safe Markdown renderer for the library documents. Everything is escaped first, so a document can never inject markup. */
(function (root) {
  'use strict';
  var MARK = '\uE000';
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function inline(s) {
    s = esc(s);
    var codes = [];
    s = s.replace(/`([^`]+)`/g, function (_, c) { codes.push(c); return MARK + (codes.length - 1) + MARK; });
    s = s.replace(/!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, function (_, a, b) { return b || a; });
    s = s.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/|#)[^)\s]*)\)/g, '<a href="$2" rel="noreferrer">$1</a>');
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])/g, '$1<em>$2</em>');
    s = s.replace(/(^|[^\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])/g, '$1<em>$2</em>');
    return s.replace(new RegExp(MARK + '(\\d+)' + MARK, 'g'), function (_, i) { return '<code>' + codes[+i] + '</code>'; });
  }
  function cells(line) { return line.trim().replace(/^\||\|$/g, '').split('|').map(function (c) { return c.trim(); }); }
  function render(md) {
    var lines = String(md || '').replace(/\r\n/g, '\n').split('\n'), out = [], para = [], i = 0;
    function flush() { if (para.length) { out.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; } }
    var LIST = /^\s*([-*+]|\d+\.)\s/;
    while (i < lines.length) {
      var s = lines[i].trim(), m;
      if (!s) { flush(); i++; }
      else if (s.indexOf('```') === 0) { flush(); i++; var code = []; while (i < lines.length && lines[i].trim().indexOf('```') !== 0) code.push(lines[i++]); i++; out.push('<pre>' + esc(code.join('\n')) + '</pre>'); }
      else if ((m = /^(#{1,6})\s+(.*)$/.exec(s))) { flush(); var n = Math.min(m[1].length + 1, 6); out.push('<h' + n + '>' + inline(m[2].trim()) + '</h' + n + '>'); i++; }
      else if (/^(-{3,}|\*{3,}|_{3,})$/.test(s)) { flush(); out.push('<hr>'); i++; }
      else if (s[0] === '|' && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        flush(); var head = cells(s), rows = []; i += 2;
        while (i < lines.length && lines[i].trim()[0] === '|') rows.push(cells(lines[i++]));
        out.push('<div class="tscroll"><table class="t"><thead><tr>' + head.map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') + '</tr></thead><tbody>' +
          rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table></div>');
      }
      else if (s[0] === '>') { flush(); var q = []; while (i < lines.length && lines[i].trim()[0] === '>') q.push(lines[i++].trim().replace(/^>+\s*/, '')); out.push('<blockquote>' + inline(q.join(' ')) + '</blockquote>'); }
      else if (LIST.test(lines[i])) {
        flush(); var ordered = /^\d+\./.test(s), items = [];
        while (i < lines.length && LIST.test(lines[i])) {
          items.push(lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, '')); i++;
          while (i < lines.length && lines[i].trim() && !LIST.test(lines[i]) && lines[i][0] === ' ') items[items.length - 1] += ' ' + lines[i++].trim();
        }
        var tag = ordered ? 'ol' : 'ul';
        out.push('<' + tag + '>' + items.map(function (x) { return '<li>' + inline(x) + '</li>'; }).join('') + '</' + tag + '>');
      }
      else { para.push(s); i++; }
    }
    flush();
    return out.join('\n');
  }
  root.TadpoleMd = { render: render };
})(typeof window !== 'undefined' ? window : globalThis);
