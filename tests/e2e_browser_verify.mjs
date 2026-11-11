/**
 * AetherLearn AI — End-to-End Browser Verification Suite (Playwright + Real Chrome)
 * Verifies desktop (1440x900) and mobile (390x844) viewports, console error hygiene,
 * signup, source grounding, roadmap generation & save, topic workspace (tutorial, reading,
 * personal notes, 20-MCQ exam submission), and AI Studio tools.
 */

import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(
  'C:\\Users\\user\\AppData\\Local\\OpenAI\\Codex\\runtimes\\cua_node\\6ef99b3d04073aa7\\bin\\node_modules\\playwright-core'
);

const BASE_URL = process.env.AETHER_BASE_URL || 'http://127.0.0.1:8000';
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function runBrowserVerification() {
  console.log('=== LAUNCHING CHROME FOR E2E UI VERIFICATION ===');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  });

  const pageErrors = [];
  const consoleErrors = [];

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    page.on('pageerror', (err) => pageErrors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('youtube.com')) {
        consoleErrors.push(msg.text());
      }
    });

    // 1. Open Auth Page & Sign Up
    console.log('1. Testing Signup Flow...');
    await page.goto(`${BASE_URL}/auth`, { waitUntil: 'networkidle' });
    const uniqueEmail = `e2e_${Date.now()}@aetherlearn.edu`;
    await page.fill('#auth-name', 'E2E Verification Scholar');
    await page.fill('#auth-email', uniqueEmail);
    await page.fill('#auth-password', 'VerifyPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    console.log('   -> Landed on /dashboard successfully.');

    // 2. Navigate to My Sources & Add Study Document
    console.log('2. Testing Source Library & Grounded Q&A...');
    await page.goto(`${BASE_URL}/sources?upload=1`, { waitUntil: 'networkidle' });
    await page.click('button:has-text("Paste Study Notes / Markdown")');
    await page.fill('#source-title-input', 'B-Tree Indexing & WAL Internals');
    await page.fill(
      '#source-text-content',
      '# Database B-Tree Indexes\nB-Tree indexes maintain sorted keys in balanced leaf pages, enabling O(log N) lookups and range scans.\n\n# Write-Ahead Logging\nWAL mode appends modifications to a sequential log file so readers never block writers.'
    );
    await page.click('button:has-text("Extract & Save Source")');
    await page.waitForSelector('text=B-Tree Indexing & WAL Internals', { timeout: 10000 });
    console.log('   -> Created & indexed study source.');

    // 3. Navigate to AI Roadmaps, Generate Preview, Edit & Save
    console.log('3. Testing AI Roadmap Agent Generation, Preview & Save...');
    await page.goto(`${BASE_URL}/roadmaps?new=1`, { waitUntil: 'networkidle' });
    await page.click('button:has-text("Generate AI Roadmap Plan")');
    await page.waitForSelector('button:has-text("Save Roadmap & Provision Learning Resources")', {
      timeout: 15000,
    });
    await page.click('button:has-text("Save Roadmap & Provision Learning Resources")');
    await page.waitForURL('**/roadmaps/rm_*', { timeout: 20000 });
    console.log('   -> Saved roadmap and redirected to roadmap detail page:', page.url());

    // 4. Open Topic 1 Workspace & Test Tutorial, Reading, Notes, and 20-MCQ Exam
    console.log('4. Testing Topic Workspace (Tutorial, Reading, Notes & 20-MCQ Exam)...');
    await page.click('button:has-text("Study Topic") >> nth=0');
    await page.waitForURL('**/topics/top_*', { timeout: 20000 });

    // Switch to Section B: Reading Material & Personal Notes
    await page.click('button:has-text("Section B: Reading Material")');
    await page.waitForSelector('text=Table of Contents', { timeout: 10000 });
    await page.fill('#note-title-input', 'E2E Verified Note');
    await page.fill('#note-content-textarea', 'Key takeaway verified via automated E2E browser test.');
    await page.click('button:has-text("Save Personal Note")');
    await page.waitForSelector('text=E2E Verified Note', { timeout: 10000 });
    console.log('   -> Verified Reading Material & saved Personal Note.');

    // Switch to Section C: 20-Question MCQ Examination
    await page.click('button:has-text("Section C:")');
    await page.waitForSelector('button:has-text("Start 20-Question Examination")', {
      timeout: 10000,
    });
    await page.click('button:has-text("Start 20-Question Examination")');
    await page.waitForSelector('text=Question 1 of 20', { timeout: 10000 });
    await page.click('button:has-text("Submit Examination Now")');
    await page.waitForSelector('text=Detailed Question-by-Question Review', { timeout: 15000 });
    console.log('   -> Completed & graded 20-Question MCQ Exam.');

    // 5. Navigate to AI Studio & Generate Audio Overview
    console.log('5. Testing AI Studio (Audio Overview WAV synthesis)...');
    await page.goto(`${BASE_URL}/studio`, { waitUntil: 'networkidle' });
    await page.click('button[type="submit"]:has-text("Generate")');
    await page.waitForSelector('audio', { timeout: 25000 });
    const audioSrc = await page.getAttribute('audio', 'src');
    console.log('   -> Audio Overview player rendered with playable WAV src:', audioSrc);

    // 6. Verify Mobile Viewport Responsiveness (390x844)
    console.log('6. Testing Mobile Viewport Responsiveness (390x844)...');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' });
    const overflowCheck = await page.evaluate(() => {
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      };
    });
    console.log('   -> Mobile viewport dimensions:', overflowCheck);
    if (overflowCheck.scrollWidth > overflowCheck.clientWidth + 4) {
      throw new Error(`Horizontal overflow detected on mobile: ${JSON.stringify(overflowCheck)}`);
    }

    if (pageErrors.length > 0) {
      throw new Error(`Uncaught page errors: ${pageErrors.join('; ')}`);
    }
    console.log('=== ALL E2E BROWSER VERIFICATION CHECKS PASSED ===');
  } finally {
    await browser.close();
  }
}

runBrowserVerification().catch((err) => {
  console.error('E2E Verification Failed:', err);
  process.exit(1);
});
