// Token budget estimator: a transparent, relative cost model (no real prices).
import { $ } from './util.js';

export function initCost() {
  const ids = ['prompt', 'ctx', 'cache', 'route', 'price'];
  const el = Object.fromEntries(ids.map((k) => [k, $(`#c-${k}`)]));
  if (!el.prompt) return;
  const OUTPUT = 500; // output tokens per request, held constant

  function update() {
    const prompt = Number(el.prompt.value);
    const ctx = Number(el.ctx.value) / 100;
    const cache = Number(el.cache.value) / 100;
    const route = Number(el.route.value) / 100;
    const price = Number(el.price.value);
    $('#o-prompt').textContent = prompt.toLocaleString('en-US');
    $('#o-ctx').textContent = `${Math.round(ctx * 100)}%`;
    $('#o-cache').textContent = `${Math.round(cache * 100)}%`;
    $('#o-route').textContent = `${Math.round(route * 100)}%`;
    $('#o-price').textContent = `${price.toFixed(2)}×`;

    // Large-model-equivalent tokens for 1,000 requests.
    const baseline = 1000 * (prompt + OUTPUT);
    const perReq = prompt * (1 - ctx) + OUTPUT;
    const misses = 1000 * (1 - cache);
    const optimized = misses * perReq * ((1 - route) + route * price);
    const units = (x) => (x / baseline) * 100;
    const save = 1 - optimized / baseline;

    $('#v-base').textContent = '100 units';
    $('#v-opt').textContent = `${units(optimized).toFixed(1)} units`;
    $('#b-opt').style.width = `${Math.max(1, units(optimized))}%`;
    $('#v-save').textContent = `−${(save * 100).toFixed(0)}%`;
  }
  ids.forEach((k) => el[k].addEventListener('input', update));
  update();
}
