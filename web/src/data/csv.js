// Minimal RFC-4180 CSV parser used at build time. Handles quoted fields,
// escaped double-quotes, and embedded newlines/commas (the result CSVs contain
// multi-line `preview` columns).

export function parseCsv(text) {
  const rows = [];
  let field = '';
  let record = [];
  let inQuotes = false;

  // Normalise line endings so embedded \r\n previews parse consistently.
  const src = text.replace(/\r\n?/g, '\n');

  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i];

    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      record.push(field);
      field = '';
    } else if (ch === '\n') {
      record.push(field);
      rows.push(record);
      record = [];
      field = '';
    } else {
      field += ch;
    }
  }

  // Flush trailing field/record (file without final newline).
  if (field.length > 0 || record.length > 0) {
    record.push(field);
    rows.push(record);
  }

  if (rows.length === 0) return [];

  const header = rows[0];
  const out = [];
  for (let r = 1; r < rows.length; r += 1) {
    const cols = rows[r];
    if (cols.length === 1 && cols[0] === '') continue; // skip blank lines
    const obj = {};
    for (let c = 0; c < header.length; c += 1) {
      obj[header[c]] = cols[c] ?? '';
    }
    out.push(obj);
  }
  return out;
}