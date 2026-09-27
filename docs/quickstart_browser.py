# Browser half of docs/screenshots/autolineage-quickstart.gif. Run examples/pipeline.py first so trace.html exists,
# then: python docs/quickstart_browser.py  -> browser.webm. Needs playwright + chromium.
import asyncio, glob, shutil
from playwright.async_api import async_playwright
CURSOR = """
const c=document.createElement('div');c.id='fakecur';
c.style.cssText='position:fixed;z-index:99999;width:0;height:0;pointer-events:none;left:0;top:0;';
c.innerHTML='<svg width="22" height="30" viewBox="0 0 22 30"><path d="M2 2 L2 24 L8 18 L12 28 L16 26 L12 17 L20 17 Z" fill="#111" stroke="#fff" stroke-width="1.5"/></svg>';
document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(c));
document.addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px';},true);
"""
async def glide(pg, x0,y0,x1,y1, steps=25, ms=12):
    for i in range(1,steps+1):
        await pg.mouse.move(x0+(x1-x0)*i/steps, y0+(y1-y0)*i/steps); await pg.wait_for_timeout(ms)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width":1000,"height":640}, record_video_dir="video", record_video_size={"width":1000,"height":640})
        pg = await ctx.new_page()
        await pg.add_init_script(CURSOR)
        await pg.goto("file://" + __import__("os").path.abspath("trace.html") + "")
        await pg.mouse.move(500,500)
        await pg.wait_for_timeout(1200)
        await glide(pg,500,500,31,124)
        for _ in range(4):
            await pg.mouse.click(31,124); await pg.wait_for_timeout(350)
        await pg.wait_for_timeout(500)
        await glide(pg,31,124,257,382)          # 5. filter
        await pg.mouse.click(257,382)
        await pg.wait_for_timeout(2800)
        # pan left to reveal train / predict / f1
        await glide(pg,257,382,600,300, steps=10)
        await pg.mouse.down(); await glide(pg,600,300,120,300, steps=30, ms=16); await pg.mouse.up()
        await pg.wait_for_timeout(400)
        await pg.screenshot(path="after_pan.png")
        info = await pg.evaluate("""() => Array.from(document.querySelectorAll('rect.node-rect')).map(e=>{const r=e.getBoundingClientRect(); return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)]})""")
        print(info)
        fx,fy = info[-1]
        if 0 < fx < 680:
            await glide(pg,120,300,fx,fy); await pg.mouse.click(fx,fy)
        await pg.wait_for_timeout(4000)
        await pg.screenshot(path="after_click.png")
        await pg.wait_for_timeout(1500)
        await ctx.close(); await b.close()
        v = sorted(glob.glob("video/*.webm"))[-1]; shutil.move(v, "browser.webm"); print("saved browser.webm")
asyncio.run(main())
