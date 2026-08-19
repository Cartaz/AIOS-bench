#!/usr/bin/env ts-node
/**
 * Monthly Expense Summary Tool
 *
 * Reads `data/expenses.csv` and produces a categorized expense report
 * at `reports/monthly-expenses.md`, following the preference for
 * simplicity and TypeScript-based automation tools.
 *
 * Usage: npx ts-node tools/monthly_expenses.ts
 */

import * as fs from "fs";
import * as path from "path";

interface ExpenseRow {
  date: string;
  category: string;
  description: string;
  amount: number;
}

/** Parse the CSV file and return validated rows. */
function loadExpenses(csvPath: string): ExpenseRow[] {
  if (!fs.existsSync(csvPath)) {
    process.stderr.write(`Error: ${csvPath} not found.\n`);
    process.exit(1);
  }

  const lines = fs.readFileSync(csvPath, "utf-8").trim().split("\n");
  const header = lines[0].split(",").map((h) => h.trim());

  const expectedHeaders = ["date", "category", "description", "amount"];
  if (!expectedHeaders.every((h) => header.includes(h))) {
    process.stderr.write(
      `Error: expected headers ${expectedHeaders}, got ${header}\n`
    );
    process.exit(1);
  }

  return lines.slice(1).map((line) => {
    const fields = line.split(",").map((f) => f.trim());
    return {
      date: fields[0],
      category: fields[1],
      description: fields[2],
      amount: parseFloat(fields[3]),
    };
  });
}

/** Group expenses by category and compute totals. */
function summarize(rows: ExpenseRow[]): Map<string, { total: number; count: number }> {
  const summary = new Map<string, { total: number; count: number }>();

  for (const row of rows) {
    const entry = summary.get(row.category) ?? { total: 0, count: 0 };
    entry.total += row.amount;
    entry.count += 1;
    summary.set(row.category, entry);
  }

  // Sort by total descending
  return new Map(
    [...summary.entries()].sort((a, b) => b[1].total - a[1].total)
  );
}

/** Write a Markdown report. */
function saveReport(summary: Map<string, { total: number; count: number }>, outputPath: string): void {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  const grandTotal = [...summary.values()].reduce((sum, v) => sum + v.total, 0);

  let md = "# Monthly Expense Summary\n\n";
  md += `| Category     | Total   | Count |\n`;
  md += `|--------------|---------|-------|\n`;

  for (const [category, stats] of summary) {
    md += `| ${category.padEnd(12)} | ${stats.total.toFixed(2).padStart(7)} | ${String(stats.count).padStart(5)} |\n`;
  }

  md += `| **Total**    | **${grandTotal.toFixed(2).padStart(7)}** | **${summary.size}** |\n`;

  fs.writeFileSync(outputPath, md, "utf-8");
  console.log(`Report saved to ${outputPath}`);
}

/** Main entry point. */
function main(): void {
  const workspace = path.resolve(__dirname, "..");
  const csvPath = path.join(workspace, "data", "expenses.csv");
  const outputPath = path.join(workspace, "reports", "monthly-expenses.md");

  const rows = loadExpenses(csvPath);
  const summary = summarize(rows);
  saveReport(summary, outputPath);
}

main();
