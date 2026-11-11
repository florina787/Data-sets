import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { mesh } from "topojson-client";
import { GeoIncident, GeoNode, RISK_RED, TIER_COLOR, TIER_LABEL } from "./geoData";
import type { MapProps } from "./Map2D";

const R = 1;

function toVec(lat: number, lon: number, r = R): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180), theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
}

function arcCurve(a: THREE.Vector3, b: THREE.Vector3): THREE.QuadraticBezierCurve3 {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const lift = 1 + 0.18 + a.distanceTo(b) * 0.28;
  return new THREE.QuadraticBezierCurve3(a, mid.normalize().multiplyScalar(lift), b);
}

const atmosphereShader = {
  vertexShader: `varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `varying vec3 vN; void main(){ float i = pow(0.72 - dot(vN, vec3(0.0,0.0,1.0)), 3.0); gl_FragColor = vec4(0.22,0.74,0.97,1.0) * i; }`,
};

/** Cinematic globe: glowing coastlines, atmosphere, arcs, pulsing risk markers, camera fly-to. */
export default function Globe3D({ net, scope, onSelect, formatValue, simulated, reducedMotion, onRendered }: MapProps) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<{ fly: (lat: number, lon: number, dist: number) => void; update: () => void } | null>(null);
  const state = useRef({ scope, simulated, reducedMotion });
  state.current = { scope, simulated, reducedMotion };
  const [hover, setHover] = useState<{ x: number; y: number; title: string; lines: string[] } | null>(null);

  useEffect(() => {
    const el = host.current!;
    const t0 = performance.now();
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, el.clientWidth / el.clientHeight, 0.05, 50);
    camera.position.set(0, 0.9, 3.1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 1.25;
    controls.maxDistance = 5;
    controls.rotateSpeed = 0.5;
    controls.autoRotate = !state.current.reducedMotion;
    controls.autoRotateSpeed = 0.35;
    controls.addEventListener("start", () => { controls.autoRotate = false; });

    scene.add(new THREE.AmbientLight(0x6b8cc7, 0.9));
    const sun = new THREE.DirectionalLight(0xbfe6ff, 1.1);
    sun.position.set(3, 2, 4);
    scene.add(sun);

    const globe = new THREE.Group();
    scene.add(globe);
    globe.add(new THREE.Mesh(new THREE.SphereGeometry(R, 96, 96),
      new THREE.MeshPhongMaterial({ color: 0x0a1c33, emissive: 0x06142a, shininess: 18, specular: 0x1d4ed8 })));
    const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(R * 1.12, 64, 64), new THREE.ShaderMaterial({
      ...atmosphereShader, blending: THREE.AdditiveBlending, side: THREE.BackSide, transparent: true, depthWrite: false }));
    scene.add(atmosphere);

    // Glowing coastlines and borders: a crisp line plus a soft additive halo.
    const borderGroup = new THREE.Group();
    globe.add(borderGroup);
    import("world-atlas/countries-110m.json").then((m: any) => {
      const topo = m.default ?? m;
      const lines = mesh(topo, topo.objects.countries) as any;
      const pts: THREE.Vector3[] = [];
      for (const line of lines.coordinates as number[][][]) {
        for (let i = 1; i < line.length; i++) {
          pts.push(toVec(line[i - 1][1], line[i - 1][0], R * 1.001), toVec(line[i][1], line[i][0], R * 1.001));
        }
      }
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      borderGroup.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.55 })));
      const halo = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending }));
      halo.scale.setScalar(1.003);
      borderGroup.add(halo);
      onRendered?.(Math.round(performance.now() - t0));
    });

    // Sites
    const byId = new Map(net.nodes.map((n) => [n.id, n]));
    const nodeMeshes: THREE.Mesh[] = [];
    const dotGeo = new THREE.SphereGeometry(0.011, 12, 12);
    for (const n of net.nodes) {
      const m = new THREE.Mesh(dotGeo, new THREE.MeshBasicMaterial({ color: TIER_COLOR[n.tier], transparent: true }));
      m.position.copy(toVec(n.lat, n.lon, R * 1.004));
      m.userData = { kind: "node", node: n };
      if (n.tier === "market") m.scale.setScalar(1.3);
      globe.add(m);
      nodeMeshes.push(m);
    }
    // Arcs
    const arcs: { line: THREE.Line; curve: THREE.QuadraticBezierCurve3; from: string; to: string; dot: THREE.Mesh; speed: number }[] = [];
    for (const e of net.edges) {
      const a = byId.get(e.from)!, b = byId.get(e.to)!;
      const curve = arcCurve(toVec(a.lat, a.lon, R * 1.004), toVec(b.lat, b.lon, R * 1.004));
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),
        new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
      globe.add(line);
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.007, 8, 8), new THREE.MeshBasicMaterial({ color: 0xf3d18a }));
      dot.visible = false;
      globe.add(dot);
      arcs.push({ line, curve, from: e.from, to: e.to, dot, speed: 1 / (4 + e.lead_time_days / 3) });
    }
    // Quality incidents: red markers with a pulsing ring (high severity / selected).
    const incGroup = new THREE.Group();
    globe.add(incGroup);
    const ringGeo = new THREE.RingGeometry(0.016, 0.021, 32);
    const incMeshes: THREE.Mesh[] = [];
    const rings: THREE.Mesh[] = [];
    for (const i of net.incidents) {
      const pos = toVec(i.lat, i.lon, R * 1.006);
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.008, 10, 10), new THREE.MeshBasicMaterial({ color: RISK_RED, transparent: true, opacity: i.severity === "low" ? 0.55 : 1 }));
      m.position.copy(pos);
      m.userData = { kind: "incident", incident: i };
      incGroup.add(m);
      incMeshes.push(m);
      if (i.severity === "high") {
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: RISK_RED, transparent: true, side: THREE.DoubleSide, depthWrite: false }));
        ring.position.copy(pos);
        ring.lookAt(pos.clone().multiplyScalar(2));
        ring.userData = { incident: i, phase: Math.random() * Math.PI * 2 };
        incGroup.add(ring);
        rings.push(ring);
      }
    }

    const update = () => {
      const { scope: s, simulated: sim, reducedMotion: rm } = state.current;
      for (const m of nodeMeshes) {
        const on = s.nodeIds.has(m.userData.node.id);
        (m.material as THREE.MeshBasicMaterial).opacity = on ? 1 : 0.15;
        m.scale.setScalar((m.userData.node.tier === "market" ? 1.3 : 1) * (s.node?.id === m.userData.node.id ? 1.35 : 1));
      }
      for (const a of arcs) {
        const on = s.nodeIds.has(a.from) && s.nodeIds.has(a.to);
        const mat = a.line.material as THREE.LineBasicMaterial;
        mat.opacity = on ? (s.all ? 0.35 : 0.9) : 0.04;
        mat.color.set(on && !s.all ? 0xe9b95b : 0x38bdf8);
        a.dot.visible = sim && on && !rm;
      }
      const ids = new Set(s.incidents.map((i) => i.id));
      for (const m of [...incMeshes, ...rings]) m.visible = ids.has(m.userData.incident.id);
    };
    update();

    // Camera fly-to (instant with reduced motion)
    let flight: { from: THREE.Vector3; to: THREE.Vector3; t0: number } | null = null;
    const fly = (lat: number, lon: number, dist: number) => {
      const to = toVec(lat, lon, dist).applyMatrix4(globe.matrixWorld);
      controls.autoRotate = false;
      if (state.current.reducedMotion) { camera.position.copy(to); return; }
      flight = { from: camera.position.clone(), to, t0: performance.now() };
    };
    api.current = { fly, update };

    // Hover + click picking
    const ray = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const pick = (ev: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      pointer.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      ray.params.Points = { threshold: 0.02 };
      const hit = ray.intersectObjects([...incMeshes.filter((m) => m.visible), ...nodeMeshes], false)[0];
      return { hit, x: ev.clientX - r.left, y: ev.clientY - r.top };
    };
    let downAt = { x: 0, y: 0 };
    const onMove = (ev: PointerEvent) => {
      const { hit, x, y } = pick(ev);
      renderer.domElement.style.cursor = hit ? "pointer" : "grab";
      if (!hit) return setHover(null);
      const d = hit.object.userData;
      if (d.kind === "node") {
        const n: GeoNode = d.node;
        setHover({ x, y, title: n.name, lines: [`${TIER_LABEL[n.tier]} · ${n.country_name}`, `Revenue dependent: ${formatValue(n.revenue_dependent)}`,
          `On time ${n.performance.on_time_pct}% · quality pass ${n.performance.quality_pass_pct}%`, "SYNTHETIC site (approximate location)"] });
      } else {
        const i: GeoIncident = d.incident;
        setHover({ x, y, title: `${i.kind} (${i.id})`, lines: [`${i.date} · ${i.severity} severity · lot ${i.batch}`,
          i.provenance === "operational_record" ? "OPERATIONAL RECORD (your inspection)" : "SYNTHETIC historical incident"] });
      }
    };
    const onDown = (ev: PointerEvent) => { downAt = { x: ev.clientX, y: ev.clientY }; };
    const onUp = (ev: PointerEvent) => {
      if (Math.hypot(ev.clientX - downAt.x, ev.clientY - downAt.y) > 4) return; // a drag, not a click
      const { hit } = pick(ev);
      if (!hit) return;
      const d = hit.object.userData;
      if (d.kind === "node") onSelect({ country: d.node.country, node: d.node.id });
      else onSelect({ country: d.incident.country, node: d.incident.node_id, incident: d.incident.id });
    };
    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);
    renderer.domElement.addEventListener("pointerleave", () => setHover(null));

    // Render loop: paused while hidden or off-screen.
    let visible = true;
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(el);
    const ro = new ResizeObserver(() => {
      renderer.setSize(el.clientWidth, el.clientHeight);
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
    });
    ro.observe(el);
    let raf = 0;
    const clock = new THREE.Clock();
    const loop = () => {
      raf = requestAnimationFrame(loop);
      if (!visible || document.hidden) return;
      const t = clock.getElapsedTime();
      const rm = state.current.reducedMotion;
      if (flight) {
        const u = Math.min(1, (performance.now() - flight.t0) / 1400), e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
        const len = flight.from.length() + (flight.to.length() - flight.from.length()) * e;
        camera.position.copy(flight.from.clone().normalize().lerp(flight.to.clone().normalize(), e).normalize().multiplyScalar(len));
        if (u >= 1) flight = null;
      }
      if (!rm) {
        for (const ring of rings) {
          const p = (t * 0.9 + ring.userData.phase) % 1;
          ring.scale.setScalar(1 + p * 2.2);
          (ring.material as THREE.MeshBasicMaterial).opacity = 0.9 * (1 - p);
        }
        for (const a of arcs) if (a.dot.visible) a.dot.position.copy(a.curve.getPoint((t * a.speed) % 1));
      }
      controls.update();
      renderer.render(scene, camera);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      scene.traverse((o: any) => { o.geometry?.dispose?.(); o.material?.dispose?.(); });
      el.removeChild(renderer.domElement);
      api.current = null;
    };
  }, [net]);

  useEffect(() => { api.current?.update(); }, [scope, simulated, reducedMotion]);
  useEffect(() => {
    const target = scope.incident ?? scope.node ?? scope.country;
    if (target) api.current?.fly(target.lat, target.lon, scope.node || scope.incident ? 1.75 : 2.3);
  }, [scope.node?.id, scope.incident?.id, scope.country?.id]);

  return (
    <div className="relative">
      <div ref={host} className="h-[420px] w-full sm:h-[500px]" data-testid="globe-3d"
        role="img" aria-label={`3D globe of the synthetic supply network: ${net.nodes.length} sites, ${net.edges.length} routes, ${net.incidents.length} incidents. Drag to rotate, scroll to zoom; the table below lists everything for keyboard users.`} />
      {hover && (
        <div className="pointer-events-none absolute z-10 max-w-[260px] rounded-lg border border-surface-line bg-surface-card/95 px-3 py-2 text-xs shadow-xl backdrop-blur"
          style={{ left: Math.min(hover.x + 14, (host.current?.clientWidth ?? 600) - 270), top: hover.y + 14 }} role="tooltip">
          <div className="font-semibold text-navy-900">{hover.title}</div>
          {hover.lines.map((l) => <div key={l} className="text-navy-700">{l}</div>)}
        </div>
      )}
    </div>
  );
}
