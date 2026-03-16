(function () {
  "use strict";

  const ROOT_SELECTOR = '[data-live-logo="true"]';
  const instances = new Map();
  const finePointerMedia = window.matchMedia
    ? window.matchMedia("(hover: hover) and (pointer: fine)")
    : null;
  const reducedMotionMedia = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

  class LiveLogoInstance {
    constructor(root) {
      this.root = root;
      this.canvas = root.querySelector(".live-logo-canvas");
      this.ctx = this.canvas && this.canvas.getContext
        ? this.canvas.getContext("2d", { alpha: true, desynchronized: true })
        : null;
      if (!this.ctx) {
        return;
      }

      this.variant = root.dataset.variant === "hero" ? "hero" : "nav";
      this.animated = root.dataset.animated !== "false";
      this.interactive = root.dataset.interactive !== "false";
      this.glow = root.dataset.glow !== "false";
      this.reducedMotionMode = root.dataset.reducedMotion || "system";
      this.staticTime = this.variant === "hero" ? 1.618 : 1.07;
      this.seed = hashString(root.id || root.dataset.variant || "live-logo");
      this.hover = 0;
      this.hoverTarget = 0;
      this.frameHandle = 0;
      this.visible = true;
      this.pointerEnabled = false;
      this.bounds = { width: 0, height: 0, dpr: 1 };
      this.embers = buildEmbers(this.variant, this.seed);
      this.grain = buildGrain(this.variant, this.seed);
      this.handleFrame = this.handleFrame.bind(this);
      this.handlePointerEnter = this.handlePointerEnter.bind(this);
      this.handlePointerLeave = this.handlePointerLeave.bind(this);
      this.handleResize = this.handleResize.bind(this);

      this.syncPointerMode();
      this.resizeObserver = typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(this.handleResize)
        : null;
      if (this.resizeObserver) {
        this.resizeObserver.observe(this.root);
      }
      this.intersectionObserver = typeof IntersectionObserver !== "undefined"
        ? new IntersectionObserver((entries) => {
            for (const entry of entries) {
              if (entry.target === this.root) {
                this.visible = entry.isIntersecting;
                this.refresh();
              }
            }
          }, { threshold: 0.08 })
        : null;
      if (this.intersectionObserver) {
        this.intersectionObserver.observe(this.root);
      }

      this.handleResize();
      this.refresh();
    }

    destroy() {
      if (this.frameHandle) {
        cancelAnimationFrame(this.frameHandle);
      }
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
      }
      if (this.intersectionObserver) {
        this.intersectionObserver.disconnect();
      }
      if (this.pointerEnabled) {
        this.root.removeEventListener("pointerenter", this.handlePointerEnter);
        this.root.removeEventListener("pointerleave", this.handlePointerLeave);
      }
    }

    syncPointerMode() {
      const nextPointerEnabled = this.interactive && (!finePointerMedia || finePointerMedia.matches);
      if (nextPointerEnabled === this.pointerEnabled) {
        return;
      }
      this.pointerEnabled = nextPointerEnabled;
      if (this.pointerEnabled) {
        this.root.addEventListener("pointerenter", this.handlePointerEnter);
        this.root.addEventListener("pointerleave", this.handlePointerLeave);
        return;
      }
      this.root.removeEventListener("pointerenter", this.handlePointerEnter);
      this.root.removeEventListener("pointerleave", this.handlePointerLeave);
      this.hoverTarget = 0;
    }

    handlePointerEnter() {
      this.hoverTarget = 1;
      this.refresh();
    }

    handlePointerLeave() {
      this.hoverTarget = 0;
      this.refresh();
    }

    handleResize() {
      const rect = this.root.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width));
      const height = Math.max(1, Math.round(rect.height));
      const dprLimit = this.variant === "hero" ? 2 : 1.5;
      const dpr = Math.min(window.devicePixelRatio || 1, dprLimit);
      if (width === this.bounds.width && height === this.bounds.height && dpr === this.bounds.dpr) {
        return;
      }
      this.bounds = { width, height, dpr };
      this.canvas.width = Math.max(1, Math.round(width * dpr));
      this.canvas.height = Math.max(1, Math.round(height * dpr));
      this.canvas.style.width = width + "px";
      this.canvas.style.height = height + "px";
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.render(this.getRenderTime(), true);
    }

    prefersReducedMotion() {
      if (this.reducedMotionMode === "true") {
        return true;
      }
      if (this.reducedMotionMode === "false") {
        return false;
      }
      return !!(reducedMotionMedia && reducedMotionMedia.matches);
    }

    shouldAnimate() {
      return this.animated && !this.prefersReducedMotion() && this.visible && !document.hidden;
    }

    getRenderTime(now) {
      return this.shouldAnimate() ? (now || performance.now()) * 0.001 : this.staticTime;
    }

    refresh() {
      if (!this.ctx) {
        return;
      }
      if (this.frameHandle) {
        cancelAnimationFrame(this.frameHandle);
        this.frameHandle = 0;
      }
      this.render(this.getRenderTime(), !this.shouldAnimate());
      if (this.shouldAnimate()) {
        this.frameHandle = requestAnimationFrame(this.handleFrame);
      }
    }

    handleFrame(now) {
      this.frameHandle = 0;
      this.render(now * 0.001, false);
      if (this.shouldAnimate()) {
        this.frameHandle = requestAnimationFrame(this.handleFrame);
      }
    }

    render(time, staticFrame) {
      const ctx = this.ctx;
      const width = this.bounds.width;
      const height = this.bounds.height;
      if (!ctx || !width || !height) {
        return;
      }

      ctx.clearRect(0, 0, width, height);
      this.hover += (this.hoverTarget - this.hover) * (staticFrame ? 1 : 0.08);

      const size = Math.min(width, height);
      const radius = size * (this.variant === "hero" ? 0.22 : 0.27);
      const ballX = width * (this.variant === "hero" ? 0.46 : 0.5);
      const ballY = height * (this.variant === "hero" ? 0.68 : 0.64);
      const flameBaseX = ballX + radius * 0.46;
      const flameBaseY = ballY - radius * 0.16;
      const flameHeight = size * (this.variant === "hero" ? 0.49 : 0.41);
      const flameDrift = size * (this.variant === "hero" ? 0.22 : 0.16);
      const hoverBoost = this.hover * 0.14;

      drawShadow(ctx, ballX, ballY + radius * 1.02, radius, this.variant);

      if (this.glow) {
        drawAura(ctx, flameBaseX, flameBaseY, flameHeight, radius, hoverBoost, this.variant);
      }

      drawFlameRibbon(ctx, {
        time,
        baseX: flameBaseX,
        baseY: flameBaseY,
        height: flameHeight,
        driftX: flameDrift,
        baseWidth: radius * 0.92,
        tipWidth: radius * 0.08,
        taper: 1.22,
        speed: 1.15 + hoverBoost,
        sway: radius * 0.58,
        microSway: radius * 0.18,
        colors: ["rgba(92, 17, 8, 0.16)", "rgba(190, 52, 14, 0.48)", "rgba(255, 151, 50, 0.06)"],
        shadow: "rgba(255, 114, 28, 0.22)",
        blur: radius * 1.25,
      });
      drawFlameRibbon(ctx, {
        time: time + 0.34,
        baseX: flameBaseX - radius * 0.05,
        baseY: flameBaseY + radius * 0.02,
        height: flameHeight * 0.9,
        driftX: flameDrift * 0.88,
        baseWidth: radius * 0.7,
        tipWidth: radius * 0.07,
        taper: 1.14,
        speed: 1.42 + hoverBoost,
        sway: radius * 0.4,
        microSway: radius * 0.13,
        colors: ["rgba(167, 38, 9, 0.24)", "rgba(255, 120, 31, 0.78)", "rgba(255, 197, 96, 0.16)"],
        shadow: "rgba(255, 136, 42, 0.28)",
        blur: radius,
      });
      drawFlameRibbon(ctx, {
        time: time + 0.72,
        baseX: flameBaseX - radius * 0.12,
        baseY: flameBaseY + radius * 0.05,
        height: flameHeight * 0.72,
        driftX: flameDrift * 0.72,
        baseWidth: radius * 0.42,
        tipWidth: radius * 0.05,
        taper: 1.06,
        speed: 1.7 + hoverBoost,
        sway: radius * 0.24,
        microSway: radius * 0.09,
        colors: ["rgba(255, 151, 58, 0.2)", "rgba(255, 194, 97, 0.88)", "rgba(255, 233, 176, 0.22)"],
        shadow: "rgba(255, 196, 112, 0.18)",
        blur: radius * 0.72,
      });

      if (this.variant === "hero") {
        drawHeatShimmer(ctx, flameBaseX, flameBaseY, flameHeight, time, this.hover);
      }

      drawEmbers(ctx, this.embers, flameBaseX, flameBaseY, flameHeight, time, this.hover);
      drawBasketball(ctx, ballX, ballY, radius, time, this.grain, this.hover, this.variant);

      this.root.classList.add("live-logo-ready");
    }
  }

  function drawShadow(ctx, x, y, radius, variant) {
    ctx.save();
    const shadow = ctx.createRadialGradient(x, y, radius * 0.2, x, y, radius * 1.4);
    shadow.addColorStop(0, "rgba(12, 9, 7, 0.26)");
    shadow.addColorStop(0.7, "rgba(12, 9, 7, 0.08)");
    shadow.addColorStop(1, "rgba(12, 9, 7, 0)");
    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.ellipse(x, y, radius * (variant === "hero" ? 1.32 : 1.14), radius * 0.34, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawAura(ctx, x, y, flameHeight, radius, hoverBoost, variant) {
    ctx.save();
    ctx.globalCompositeOperation = "screen";

    const lowAura = ctx.createRadialGradient(x + radius * 0.4, y - flameHeight * 0.35, radius * 0.1, x, y, flameHeight);
    lowAura.addColorStop(0, "rgba(255, 208, 142, 0.16)");
    lowAura.addColorStop(0.42, "rgba(255, 124, 39, 0.18)");
    lowAura.addColorStop(1, "rgba(255, 124, 39, 0)");
    ctx.fillStyle = lowAura;
    ctx.beginPath();
    ctx.ellipse(x + radius * 0.2, y - flameHeight * 0.2, radius * 1.7, flameHeight * 0.92, -0.5, 0, Math.PI * 2);
    ctx.fill();

    const coreAura = ctx.createRadialGradient(x - radius * 0.2, y + radius * 0.12, radius * 0.1, x, y, radius * (1.8 + hoverBoost));
    coreAura.addColorStop(0, "rgba(255, 228, 178, 0.22)");
    coreAura.addColorStop(0.6, variant === "hero" ? "rgba(255, 130, 44, 0.18)" : "rgba(255, 130, 44, 0.14)");
    coreAura.addColorStop(1, "rgba(255, 130, 44, 0)");
    ctx.fillStyle = coreAura;
    ctx.beginPath();
    ctx.arc(x - radius * 0.16, y + radius * 0.06, radius * 1.9, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawFlameRibbon(ctx, config) {
    const points = [];
    const count = 20;
    for (let index = 0; index < count; index += 1) {
      const position = index / (count - 1);
      const lift = Math.pow(position, 1.08);
      const falloff = Math.pow(1 - position, 0.55);
      const macroWave =
        Math.sin(config.time * config.speed + position * 7.2 + 0.7) * config.sway * falloff +
        Math.sin(config.time * (config.speed * 0.61) + position * 12.8 + 1.9) * config.microSway;
      const x = config.baseX + config.driftX * lift + macroWave;
      const y = config.baseY - config.height * lift + Math.sin(config.time * 1.2 + position * 8.4) * config.microSway * 0.5;
      const width = config.tipWidth + Math.pow(1 - position, config.taper) * config.baseWidth;
      points.push({ x, y, width });
    }

    const left = [];
    const right = [];
    for (let index = 0; index < points.length; index += 1) {
      const point = points[index];
      const previous = points[Math.max(0, index - 1)];
      const next = points[Math.min(points.length - 1, index + 1)];
      const tangentX = next.x - previous.x;
      const tangentY = next.y - previous.y;
      const length = Math.max(0.001, Math.hypot(tangentX, tangentY));
      const normalX = -tangentY / length;
      const normalY = tangentX / length;
      left.push({ x: point.x + normalX * point.width * 0.5, y: point.y + normalY * point.width * 0.5 });
      right.push({ x: point.x - normalX * point.width * 0.5, y: point.y - normalY * point.width * 0.5 });
    }

    ctx.save();
    ctx.globalCompositeOperation = "screen";
    ctx.beginPath();
    ctx.moveTo(left[0].x, left[0].y);
    for (let index = 1; index < left.length; index += 1) {
      ctx.lineTo(left[index].x, left[index].y);
    }
    for (let index = right.length - 1; index >= 0; index -= 1) {
      ctx.lineTo(right[index].x, right[index].y);
    }
    ctx.closePath();

    const gradient = ctx.createLinearGradient(config.baseX, config.baseY, points[points.length - 1].x, points[points.length - 1].y);
    gradient.addColorStop(0, config.colors[0]);
    gradient.addColorStop(0.38, config.colors[1]);
    gradient.addColorStop(1, config.colors[2]);
    ctx.fillStyle = gradient;
    ctx.shadowColor = config.shadow;
    ctx.shadowBlur = config.blur;
    ctx.fill();
    ctx.restore();
  }

  function drawHeatShimmer(ctx, x, y, flameHeight, time, hover) {
    const laneOffset = flameHeight * 0.15;
    const laneGap = flameHeight * 0.065;
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    ctx.lineCap = "round";
    for (let index = 0; index < 3; index += 1) {
      const progress = index / 3;
      ctx.beginPath();
      ctx.moveTo(x + laneOffset + index * laneGap, y - flameHeight * 0.08);
      for (let step = 1; step <= 6; step += 1) {
        const lift = step / 6;
        const wave = Math.sin(time * 1.4 + step * 0.8 + index) * (flameHeight * 0.06 + hover * flameHeight * 0.03) * (1 - lift);
        ctx.lineTo(x + laneOffset + index * laneGap + wave, y - flameHeight * (0.18 + lift * 0.72));
      }
      ctx.strokeStyle = "rgba(255, 189, 111, 0.05)";
      ctx.lineWidth = flameHeight * (0.022 - progress * 0.004);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawEmbers(ctx, embers, baseX, baseY, flameHeight, time, hover) {
    const scale = flameHeight;
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    for (const ember of embers) {
      const cycle = fract(time * ember.speed + ember.phase);
      const life = cycle;
      const alpha = Math.pow(1 - life, 1.7) * ember.alpha;
      if (alpha < 0.02) {
        continue;
      }
      const x =
        baseX +
        ember.startX * scale +
        ember.driftX * scale * life +
        Math.sin((life * 7 + ember.phase) * Math.PI * 2) * ember.sway * scale * (1 - life);
      const y = baseY + ember.startY * scale - scale * ember.lift * life;
      const radius = ember.size * scale * (1 + hover * 0.12) * (0.72 + (1 - life) * 0.4);
      const glow = ctx.createRadialGradient(x, y, radius * 0.2, x, y, radius * 2.2);
      glow.addColorStop(0, "rgba(255, 236, 201, " + (alpha + 0.08).toFixed(3) + ")");
      glow.addColorStop(0.45, "rgba(255, 177, 88, " + alpha.toFixed(3) + ")");
      glow.addColorStop(1, "rgba(255, 92, 26, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, radius * 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawBasketball(ctx, x, y, radius, time, grain, hover, variant) {
    const rotation = time * 0.34;
    ctx.save();
    ctx.translate(x, y);

    const base = ctx.createRadialGradient(-radius * 0.35, -radius * 0.48, radius * 0.12, 0, 0, radius * 1.16);
    base.addColorStop(0, "#ffbf74");
    base.addColorStop(0.34, "#f08c36");
    base.addColorStop(0.72, "#a84a17");
    base.addColorStop(1, "#4c1608");
    ctx.fillStyle = base;
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.clip();

    const warmLight = ctx.createRadialGradient(radius * 0.38, -radius * 0.26, radius * 0.05, radius * 0.16, -radius * 0.12, radius * 1.1);
    warmLight.addColorStop(0, "rgba(255, 212, 146, 0.3)");
    warmLight.addColorStop(0.4, "rgba(255, 167, 84, 0.16)");
    warmLight.addColorStop(1, "rgba(255, 167, 84, 0)");
    ctx.fillStyle = warmLight;
    ctx.fillRect(-radius, -radius, radius * 2, radius * 2);

    const falloff = ctx.createLinearGradient(-radius * 0.4, -radius * 0.2, radius, radius);
    falloff.addColorStop(0, "rgba(72, 26, 11, 0)");
    falloff.addColorStop(1, "rgba(40, 8, 3, 0.4)");
    ctx.fillStyle = falloff;
    ctx.fillRect(-radius, -radius, radius * 2, radius * 2);

    ctx.fillStyle = "rgba(63, 24, 10, 0.08)";
    for (const point of grain) {
      const grainX = point.x * radius + Math.sin(rotation + point.phase) * radius * 0.02 * point.depth;
      const grainY = point.y * radius;
      const grainRadius = point.radius * radius;
      ctx.beginPath();
      ctx.ellipse(grainX, grainY, grainRadius, grainRadius * point.stretch, point.angle, 0, Math.PI * 2);
      ctx.fill();
    }

    drawSeams(ctx, radius, rotation);
    ctx.restore();

    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.lineWidth = Math.max(1.2, radius * 0.034);
    ctx.strokeStyle = "rgba(255, 209, 158, 0.3)";
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.98, -0.7, 0.34);
    ctx.lineWidth = Math.max(1.2, radius * 0.06);
    ctx.strokeStyle = "rgba(255, 219, 170, " + (0.16 + hover * 0.06).toFixed(3) + ")";
    ctx.stroke();

    ctx.globalCompositeOperation = "screen";
    const highlight = ctx.createRadialGradient(-radius * 0.34, -radius * 0.5, radius * 0.03, -radius * 0.2, -radius * 0.34, radius * 0.68);
    highlight.addColorStop(0, "rgba(255, 241, 216, 0.22)");
    highlight.addColorStop(1, "rgba(255, 241, 216, 0)");
    ctx.fillStyle = highlight;
    ctx.beginPath();
    ctx.arc(-radius * 0.18, -radius * 0.24, radius * 0.64, 0, Math.PI * 2);
    ctx.fill();

    if (variant === "hero") {
      ctx.beginPath();
      ctx.arc(radius * 0.05, -radius * 0.08, radius * 1.18, -0.45, 0.86);
      ctx.lineWidth = radius * 0.02;
      ctx.strokeStyle = "rgba(255, 143, 56, 0.16)";
      ctx.stroke();
    }

    ctx.restore();
  }

  function drawSeams(ctx, radius, rotation) {
    const sway = Math.sin(rotation) * radius * 0.16;
    const arcShift = Math.sin(rotation * 0.82) * radius * 0.04;
    ctx.save();
    ctx.rotate(-0.18);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "rgba(49, 15, 6, 0.76)";
    ctx.lineWidth = Math.max(1.3, radius * 0.085);
    ctx.shadowColor = "rgba(255, 178, 105, 0.08)";
    ctx.shadowBlur = radius * 0.08;

    strokeBezier(ctx, [
      [0, -radius],
      [-radius * 0.42 + sway, -radius * 0.66],
      [-radius * 0.42 + sway, radius * 0.66],
      [0, radius],
    ]);
    strokeBezier(ctx, [
      [0, -radius],
      [radius * 0.42 + sway, -radius * 0.66],
      [radius * 0.42 + sway, radius * 0.66],
      [0, radius],
    ]);
    strokeBezier(ctx, [
      [-radius * 0.94, -radius * 0.18 + arcShift],
      [-radius * 0.46, -radius * 0.62 + arcShift],
      [radius * 0.46, -radius * 0.62 + arcShift],
      [radius * 0.94, -radius * 0.18 + arcShift],
    ]);
    strokeBezier(ctx, [
      [-radius * 0.94, radius * 0.18 + arcShift],
      [-radius * 0.46, radius * 0.62 + arcShift],
      [radius * 0.46, radius * 0.62 + arcShift],
      [radius * 0.94, radius * 0.18 + arcShift],
    ]);

    ctx.strokeStyle = "rgba(255, 185, 118, 0.08)";
    ctx.lineWidth = Math.max(1, radius * 0.026);
    strokeBezier(ctx, [
      [0, -radius * 0.96],
      [radius * 0.36 + sway, -radius * 0.6],
      [radius * 0.36 + sway, radius * 0.6],
      [0, radius * 0.96],
    ]);
    ctx.restore();
  }

  function strokeBezier(ctx, points) {
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    ctx.bezierCurveTo(points[1][0], points[1][1], points[2][0], points[2][1], points[3][0], points[3][1]);
    ctx.stroke();
  }

  function buildEmbers(variant, seed) {
    const count = variant === "hero" ? 12 : 6;
    const items = [];
    for (let index = 0; index < count; index += 1) {
      const stream = hashString(seed + ":" + index);
      items.push({
        phase: fract(stream * 0.0013 + index * 0.17),
        speed: 0.26 + fract(stream * 0.0021) * 0.24,
        startX: (fract(stream * 0.013) - 0.3) * (variant === "hero" ? 0.32 : 0.18),
        startY: -fract(stream * 0.031) * (variant === "hero" ? 0.11 : 0.07),
        driftX: 0.16 + fract(stream * 0.021) * (variant === "hero" ? 0.34 : 0.18),
        lift: 0.52 + fract(stream * 0.029) * 0.5,
        sway: 0.02 + fract(stream * 0.037) * (variant === "hero" ? 0.06 : 0.035),
        size: 0.038 + fract(stream * 0.043) * (variant === "hero" ? 0.028 : 0.022),
        alpha: 0.16 + fract(stream * 0.051) * 0.24,
      });
    }
    return items;
  }

  function buildGrain(variant, seed) {
    const count = variant === "hero" ? 34 : 18;
    const items = [];
    for (let index = 0; index < count; index += 1) {
      const stream = hashString(seed + "|grain|" + index);
      const radius = Math.sqrt(fract(stream * 0.0043)) * 0.9;
      const angle = fract(stream * 0.0091) * Math.PI * 2;
      items.push({
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        radius: 0.012 + fract(stream * 0.0121) * (variant === "hero" ? 0.03 : 0.024),
        stretch: 0.6 + fract(stream * 0.0171) * 1.1,
        angle: fract(stream * 0.0193) * Math.PI,
        depth: 0.4 + fract(stream * 0.0211),
        phase: fract(stream * 0.0249) * Math.PI * 2,
      });
    }
    return items;
  }

  function hashString(input) {
    const text = String(input);
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function fract(value) {
    return value - Math.floor(value);
  }

  function initTree(node) {
    if (!node || node.nodeType !== 1) {
      return;
    }
    if (node.matches && node.matches(ROOT_SELECTOR)) {
      initNode(node);
    }
    if (node.querySelectorAll) {
      node.querySelectorAll(ROOT_SELECTOR).forEach(initNode);
    }
  }

  function initNode(node) {
    if (instances.has(node)) {
      return;
    }
    const instance = new LiveLogoInstance(node);
    if (instance.ctx) {
      instances.set(node, instance);
    }
  }

  function teardownTree(node) {
    if (!node || node.nodeType !== 1) {
      return;
    }
    if (instances.has(node)) {
      instances.get(node).destroy();
      instances.delete(node);
    }
    if (node.querySelectorAll) {
      node.querySelectorAll(ROOT_SELECTOR).forEach((child) => {
        if (instances.has(child)) {
          instances.get(child).destroy();
          instances.delete(child);
        }
      });
    }
  }

  function syncAll() {
    instances.forEach((instance) => {
      instance.syncPointerMode();
      instance.refresh();
    });
  }

  function boot() {
    initTree(document.body);
    if (typeof MutationObserver !== "undefined") {
      const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          mutation.addedNodes.forEach(initTree);
          mutation.removedNodes.forEach(teardownTree);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
    document.addEventListener("visibilitychange", syncAll);
    observeMediaChange(finePointerMedia, syncAll);
    observeMediaChange(reducedMotionMedia, syncAll);
  }

  function observeMediaChange(mediaQuery, listener) {
    if (!mediaQuery) {
      return;
    }
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", listener);
      return;
    }
    if (mediaQuery.addListener) {
      mediaQuery.addListener(listener);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
