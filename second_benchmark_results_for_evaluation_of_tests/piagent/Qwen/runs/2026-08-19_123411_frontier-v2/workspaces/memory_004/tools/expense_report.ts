/**
 * expense_report.ts — Reads an expenses CSV and prints a category-wise summary.
 * Built as a simple, maintainable TypeScript tool (per durable preferences).
 *
 * Usage:  npx ts-node tools/expense_report.ts [path/to/expenses.csv]
 * Default: data/expenses.csv (relative to workspace root)
 */

import * as fs from "fs";
import * as path from "path";

interface ExpenseRow {
  date: string;
  category: string;
  description: string;
  amount: number;
}

function parseCSV(filePath: string): ExpenseRow[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.trim().split("\n");

  if (lines.length < 2) {
    throw new Error("CSV file must contain a header row and at least one data row");
  }

  const header = lines[0].split(",").map((h) => h.trim());
  const expectedHeaders = ["date", "category", "description", "amount"];

  for (const expected of expectedHeaders) {
    if (!header.includes(expected)) {
      throw new Error(`Missing required header: ${expected}`);
    }
  }

  const rows: ExpenseRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",").map((c) => c.trim());
    const amount = Number(cols[header.indexOf("amount")]);

    if (isNaN(amount)) {
      throw new Error(`Row ${i + 1} contains non-numeric amount: "${lines[i]}"`);
    }

    rows.push({
      date: cols[header.indexOf("date")],
      category: cols[header.indexOf("category")],
      description: cols[header.indexOf("description")],
      amount,
    });
  }

  return rows;
}

function summarizeByCategory(rows: ExpenseRow[]): Map<string, { total: number; count: number }> {
  const map = new Map<string, { total: number; count: number }>();

  for (const row of rows) {
    const existing = map.get(row.category) || { total: 0, count: 0 };
    existing.total += row.amount;
    existing.count += 1;
    map.set(row.category, existing);
  }

  return map;
}

function main(): void {
  const csvPath = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.resolve(__dirname, "..", "data", "expenses.csv");

  if (!fs.existsSync(csvPath)) {
    console.error(`Error: file not found — ${csvPath}`);
    process.exit(1);
  }

  try {
    const rows = parseCSV(csvPath);
    const byCategory = summarizeByCategory(rows);
    let grandTotal = 0;

    console.log("=== Expense Report ===");
    for (const [category, data] of byCategory) {
      grandTotal += data.total;
      console.log(`  ${category.padEnd(12)}: $${data.total.toFixed(2)}  (${data.count} items)`);
    }
    console.log(`  ${"TOTAL".padEnd(12)}: $${grandTotal.toFixed(2)}`);
    console.log(`  Total transactions: ${rows.length}`);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

main();
