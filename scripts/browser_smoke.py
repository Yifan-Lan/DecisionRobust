"""Optional browser QA: pip install playwright; playwright install chromium.
Start the local server on port 8000, then run this script.
Screenshots go to a temporary folder.
"""
import asyncio, json, os, tempfile
BASE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000/")
SCREENSHOTS = tempfile.mkdtemp(prefix="decisionrobust-qa-")
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True, args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
  errors=[]
  page.on('pageerror',lambda err: errors.append(str(err)))
  await page.goto(BASE_URL,wait_until='networkidle')
  await page.wait_for_selector('.ground-truth')
  assert await page.locator('#results-table tbody tr').count()==30
  await page.screenshot(path=f'{SCREENSHOTS}/desktop.png',full_page=True)
  await page.locator('[data-suite="text_adversarial_curated"]').click()
  assert await page.locator('#results-table thead th').count()==5
  await page.locator('#model-search').fill('KEV')
  assert await page.locator('#results-table tbody tr').count()==2
  await page.locator('#model-search').fill('')
  await page.locator('input[data-model="jev"]').check()
  await page.locator('#selected-only').check()
  assert await page.locator('#results-table tbody tr').count()==1
  await page.locator('#reset-models').click()
  # Traverse every nonempty suite/scenario and check clean/adv renders.
  suites=await page.locator('#example-suite option').evaluate_all('(els)=>els.map(e=>e.value)')
  visited=0
  for suite in suites:
   await page.select_option('#example-suite',suite)
   scenarios=await page.locator('#scenario option').evaluate_all('(els)=>els.map(e=>e.value).filter(Boolean)')
   for scenario in scenarios:
    await page.select_option('#scenario',scenario)
    await page.wait_for_selector('.ground-truth')
    assert await page.locator('.panel').count()==2
    assert await page.locator('#sample option').count()>0
    visited+=1
  # Image requests and full-size modal.
  await page.select_option('#example-suite','image_perturbation_curated')
  await page.wait_for_selector('.panel img')
  await page.locator('.panel img').first.scroll_into_view_if_needed()
  await page.wait_for_function('Array.from(document.querySelectorAll(".panel img")).every(i=>i.complete && i.naturalWidth>0)',timeout=90000)
  await page.locator('.panel img').first.click()
  assert await page.locator('#image-dialog').is_visible()
  await page.locator('#close-image').click()
  await page.screenshot(path=f'{SCREENSHOTS}/explorer.png',full_page=True)
  url=page.url
  await page.reload(wait_until='networkidle')
  await page.wait_for_selector('.ground-truth')
  assert page.url==url
  await page.set_viewport_size({'width':390,'height':844})
  await page.goto(BASE_URL,wait_until='networkidle')
  await page.wait_for_selector('.ground-truth')
  assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
  await page.screenshot(path=f'{SCREENSHOTS}/mobile.png',full_page=True)
  assert not errors,errors
  print(json.dumps({'models':30,'suite_scenarios_tested':visited,'image_load_and_modal':'passed','share_url_reload':'passed','mobile_overflow':False,'javascript_errors':errors}))
  await browser.close()
asyncio.run(main())
