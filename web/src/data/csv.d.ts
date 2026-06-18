export type CsvRow = Record<string, string>;

export function parseCsv(text: string): CsvRow[];