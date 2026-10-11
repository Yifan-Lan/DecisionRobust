"""Browser checks for published-value charts. Start the site on port 8000 first.
Requires Playwright; SITE_URL can point at the deployed website.
"""
import asyncio,json,pathlib,os,tempfile
from playwright.async_api import async_playwright
BASE=os.environ.get('SITE_URL','http://127.0.0.1:8000/')
OUT=pathlib.Path(tempfile.mkdtemp(prefix='decisionrobust-charts-'))
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE,wait_until='networkidle');await page.wait_for_selector('.ground-truth')
  assert await page.locator('#chart-limit').input_value()=='all'
  assert await page.locator('.chart-mark').count()==30
  metrics=await page.evaluate('data.results')
  async def verify_values():
   marks=await page.locator('.chart-mark').evaluate_all('(els)=>els.map(e=>({...e.dataset}))')
   complete=await page.locator('#chart-complete').is_checked()
   for m in marks:
    rows=[r for r in metrics[m['config']] if r['denominator']>0 and (not complete or r['valid_pairs']==r['candidates'])]
    r=next(r for r in rows if r['model']==m['model'])
    assert abs(float(m['asr'])-r['asr'])<1e-12
    assert int(m['rank'])==1+sum(v['asr']<r['asr'] for v in rows)
   return len(marks)
  await verify_values()
  bars=await page.locator('.chart-mark .focus-ring').evaluate_all('(els)=>els.map(e=>({x:+e.getAttribute("x"),y:+e.getAttribute("y"),height:+e.getAttribute("height"),width:+e.getAttribute("width"),asr:+e.parentElement.dataset.asr}))')
  assert all(bars[i]['x']<bars[i+1]['x'] for i in range(len(bars)-1))
  assert all(abs(b['height']-b['asr']*270)<1e-9 and abs(b['height']+b['y']-365)<1e-9 for b in bars)
  await page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
  await page.locator('.chart-card').screenshot(path=str(OUT/'bars.png'))
  await page.locator('.chart-mark').first.focus()
  assert await page.locator('#chart-tooltip').is_visible()
  await page.keyboard.press('Escape');assert not await page.locator('#chart-tooltip').is_visible()
  async with page.expect_download() as dl:
   await page.click('#download-chart')
  download=await dl.value;await download.save_as(str(OUT/'ranking.svg'))
  for c in metrics:
   await page.select_option('#chart-suite',c);await page.select_option('#chart-limit','all');n=await verify_values()
   assert n==sum(r['denominator']>0 for r in metrics[c])
   await page.check('#chart-complete');n=await verify_values()
   assert n==sum(r['denominator']>0 and r['valid_pairs']==r['candidates'] for r in metrics[c])
   await page.uncheck('#chart-complete')
  # Line charts preserve gaps: JEV and Liquid API are text-only in these published results.
  await page.check('input[data-model="jev"]');await page.check('input[data-model="d1"]');await page.check('input[data-model="pplx"]')
  await page.click('[data-chart="lines"]');await verify_values()
  assert await page.locator('.chart-mark[data-model="jev"]').count()==2
  assert await page.locator('.chart-mark[data-model="d1"]').count()==2
  assert await page.locator('.chart-mark[data-model="pplx"]').count()==5
  await page.locator('.chart-card').screenshot(path=str(OUT/'lines.png'))
  await page.select_option('#chart-measure','rank');await verify_values()
  await page.locator('.chart-card').screenshot(path=str(OUT/'ranks.png'))
  url=page.url;await page.reload(wait_until='networkidle');await page.wait_for_selector('.chart-mark')
  assert await page.locator('[data-chart="lines"]').get_attribute('aria-pressed')=='true'
  assert await page.locator('#chart-measure').input_value()=='rank'
  assert await page.locator('.chart-mark').count()==9
  # Empty state must not invent zero-valued results.
  await page.fill('#model-search','nothingmatches_this');assert await page.locator('.chart-mark').count()==0
  assert await page.locator('#download-chart').is_disabled()
  await page.fill('#model-search','');await page.click('#reset-models')
  # Direct model picker and table selections stay synchronized.
  await page.locator('.chart-picker summary').click()
  await page.check('input[data-compare="h2o"]')
  assert await page.locator('input[data-model="h2o"]').is_checked()
  assert await page.locator('.chart-mark').count()==5
  await page.uncheck('input[data-compare="h2o"]')
  # Suite tabs and chart reference remain synchronized.
  await page.click('[data-suite="image_overlay_curated"]')
  assert await page.locator('#chart-suite').input_value()=='image_overlay_curated'
  await page.select_option('#chart-suite','text_injection_curated')
  assert await page.locator('[data-suite="text_injection_curated"]').get_attribute('aria-pressed')=='true'
  await page.set_viewport_size({'width':390,'height':844})
  await page.goto(BASE,wait_until='networkidle');await page.wait_for_selector('.ground-truth')
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  await page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
  assert not errors,errors
  result={'ranking_values':'match published ASR','ranks':'validated against eligible pool','coverage_filters':'passed for five datasets','missing_results':'gaps, not zeros','chart_url_restore':'passed','svg_export':'passed','mobile_overflow':False,'javascript_errors':errors}
  (OUT/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
  await browser.close()
asyncio.run(main())
