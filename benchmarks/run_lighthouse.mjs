import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

async function run() {
  const url = process.argv[2] || 'https://routiqo-dashboard.vercel.app';
  console.log(`Running Lighthouse audit on ${url}...`);

  const chrome = await chromeLauncher.launch({
    chromeFlags: ['--headless', '--no-sandbox', '--disable-gpu']
  });

  const options = {
    logLevel: 'error',
    output: 'json',
    onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
    port: chrome.port
  };

  try {
    const runnerResult = await lighthouse(url, options);
    const reportJson = JSON.parse(runnerResult.report);
    const categories = reportJson.categories;

    const scores = {
      url: url,
      performance: Math.round(categories.performance.score * 100),
      accessibility: Math.round(categories.accessibility.score * 100),
      bestPractices: Math.round(categories['best-practices'].score * 100),
      seo: Math.round(categories.seo.score * 100)
    };

    console.log('LIGHTHOUSE_RESULTS_START');
    console.log(JSON.stringify(scores, null, 2));
    console.log('LIGHTHOUSE_RESULTS_END');
  } catch (err) {
    console.error('Lighthouse audit failed:', err);
  } finally {
    await chrome.kill();
  }
}

run();
