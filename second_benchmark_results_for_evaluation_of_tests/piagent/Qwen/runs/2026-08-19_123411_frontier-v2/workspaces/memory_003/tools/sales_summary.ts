/**
 * sales_summary.ts — Reads a sales CSV and prints a summary of total revenue
 * and total units sold. Built as a simple, maintainable TypeScript tool.
 *
 * Usage:  npx ts-node tools/sales_summary.ts [path/to/sales.csv]
 * Default: data/sales.csv (relative to workspace root)
 */

import * as fs from "fs";
import * as path from "path";

interface SaleRow {
  date: string;
  product: string;
  units: number;
  revenue: number;
}

function parseCSV(filePath: string): SaleRow[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.trim().split("\n");

  if (lines.length < 2) {
    throw new Error("CSV file must contain a header row and at least one data row");
  }

  const header = lines[0].split(",").map((h) => h.trim());
  const expectedHeaders = ["date", "product", "units", "revenue"];

  for (const expected of expectedHeaders) {
    if (!header.includes(expected)) {
      throw new Error(`Missing required header: ${expected}`);
    }
  }

  const rows: SaleRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",").map((c) => c.trim());
    const units = Number(cols[header.indexOf("units")]);
    const revenue = Number(cols[header.indexOf("revenue")]);

    if (isNaN(units) || isNaN(revenue)) {
      throw new Error(`Row ${i + 1} contains non-numeric units or revenue: "${lines[i]}"`);
    }

    rows.push({
      date: cols[header.indexOf("date")],
      product: cols[header.indexOf("product")],
      units,
      revenue,
    });
  }

  return rows;
}

function summarize(rows: SaleRow[]): { totalRevenue: number; totalUnits: number; count: number } {
  let totalRevenue = 0;
  let totalUnits = 0;

  for (const row of rows) {
    totalRevenue += row.revenue;
    totalUnits += row.units;
  }

  return { totalRevenue, totalUnits, count: rows.length };
}

function main(): void {
  const csvPath = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.resolve(__dirname, "..", "data", "sales.csv");

  if (!fs.existsSync(csvPath)) {
    console.error(`Error: file not found — ${csvPath}`);
    process.exit(1);
  }

  try {
    const rows = parseCSV(csvPath);
    const summary = summarize(rows);

    console.log("=== Sales Summary ===");
    console.log(`Transactions : ${summary.count}`);
    console.log(`Total units  : ${summary.totalUnits}`);
    console.log(`Total revenue: $${summary.totalRevenue.toFixed(2)}`);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

main();
