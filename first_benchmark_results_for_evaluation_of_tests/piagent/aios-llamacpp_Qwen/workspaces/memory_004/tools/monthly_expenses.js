#!/usr/bin/env ts-node
"use strict";
/**
 * Monthly Expense Summary Tool
 *
 * Reads `data/expenses.csv` and produces a categorized expense report
 * at `reports/monthly-expenses.md`, following the preference for
 * simplicity and TypeScript-based automation tools.
 *
 * Usage: npx ts-node tools/monthly_expenses.ts
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/** Parse the CSV file and return validated rows. */
function loadExpenses(csvPath) {
    if (!fs.existsSync(csvPath)) {
        process.stderr.write(`Error: ${csvPath} not found.\n`);
        process.exit(1);
    }
    const lines = fs.readFileSync(csvPath, "utf-8").trim().split("\n");
    const header = lines[0].split(",").map((h) => h.trim());
    const expectedHeaders = ["date", "category", "description", "amount"];
    if (!expectedHeaders.every((h) => header.includes(h))) {
        process.stderr.write(`Error: expected headers ${expectedHeaders}, got ${header}\n`);
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
function summarize(rows) {
    const summary = new Map();
    for (const row of rows) {
        const entry = summary.get(row.category) ?? { total: 0, count: 0 };
        entry.total += row.amount;
        entry.count += 1;
        summary.set(row.category, entry);
    }
    // Sort by total descending
    return new Map([...summary.entries()].sort((a, b) => b[1].total - a[1].total));
}
/** Write a Markdown report. */
function saveReport(summary, outputPath) {
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
function main() {
    const workspace = path.resolve(__dirname, "..");
    const csvPath = path.join(workspace, "data", "expenses.csv");
    const outputPath = path.join(workspace, "reports", "monthly-expenses.md");
    const rows = loadExpenses(csvPath);
    const summary = summarize(rows);
    saveReport(summary, outputPath);
}
main();
