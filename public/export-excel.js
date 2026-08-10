/* 表格数据导出为 Excel（.xlsx）。
 * 依赖：本地 vendor 的 xlsx.full.min.js（SheetJS）。若该脚本未加载（离线 / CDN 失败），
 * 自动降级为带 UTF-8 BOM 的 CSV —— Excel 可直接打开，中文不乱码。
 * 用法：HouchuExport.exportTable(headers, rows, filename)
 *   headers: ["列1","列2",...]
 *   rows:    [{列1:值, 列2:值, ...}, ...]（键名须与 headers 中字符串一致）
 */
(function () {
  'use strict';

  function safeVal(v) {
    if (v === undefined || v === null) return '';
    return v;
  }

  function buildAoa(headers, rows) {
    var head = headers.map(function (h) { return safeVal(h); });
    var body = rows.map(function (r) {
      return headers.map(function (h) {
        return safeVal(r[h]);
      });
    });
    return [head].concat(body);
  }

  function downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function exportCsv(headers, rows, filename) {
    var aoa = buildAoa(headers, rows);
    var csv = '﻿' + aoa.map(function (line) {
      return line.map(function (c) {
        var s = String(c);
        if (/[",\n\r]/.test(s)) s = '"' + s.replace(/"/g, '""') + '"';
        return s;
      }).join(',');
    }).join('\r\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, filename.replace(/\.xlsx$/i, '.csv'));
  }

  function exportXlsx(headers, rows, filename) {
    var aoa = buildAoa(headers, rows);
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    ws['!cols'] = headers.map(function (h) {
      return { wch: Math.max(10, String(h).length * 2 + 2) };
    });
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '数据');
    XLSX.writeFile(wb, filename);
  }

  function exportTable(headers, rows, filename) {
    filename = filename || ('export-' + Date.now() + '.xlsx');
    if (!/\.(xlsx|csv)$/i.test(filename)) filename += '.xlsx';
    if (!Array.isArray(headers) || !headers.length) {
      console.warn('HouchuExport: headers 为空');
      return;
    }
    rows = Array.isArray(rows) ? rows : [];
    try {
      if (window.XLSX && typeof XLSX.utils !== 'undefined') {
        exportXlsx(headers, rows, filename);
        return;
      }
    } catch (e) {
      console.warn('SheetJS 导出失败，降级 CSV：', e);
    }
    exportCsv(headers, rows, filename);
  }

  window.HouchuExport = { exportTable: exportTable };
})();
