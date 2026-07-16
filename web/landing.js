/* ==========================================
   Lyra Landing Page — Interactive Logic
   Drifting Constellations, Theme Toggle,
   Expandable Features, Radar, Counters
   ========================================== */

document.addEventListener("DOMContentLoaded", () => {
    generateStardustBackground();
    window.addEventListener("resize", generateStardustBackground);
    setupScrollReveals();
    setupDemoAnimations();
    setupDriftingConstellations();
    setupThemeToggle();
    setupExpandableFeatures();
    setupStatCounters();
});

// ==========================================
// Twinkling Stars
// ==========================================
function generateStardustBackground() {
    const container = document.getElementById("twinkling-stars");
    if (!container) return;
    container.innerHTML = "";
    const speeds = ["twinkle-slow", "twinkle-mid", "twinkle-fast"];
    const count = Math.floor((window.innerWidth * window.innerHeight) / 18000) + 20;
    for (let i = 0; i < count; i++) {
        const star = document.createElement("div");
        star.className = `star ${speeds[Math.floor(Math.random() * speeds.length)]}`;
        const size = (Math.random() * 1.5 + 1).toFixed(1);
        star.style.width = `${size}px`;
        star.style.height = `${size}px`;
        star.style.left = `${Math.random() * 100}%`;
        star.style.top = `${Math.random() * 100}%`;
        star.style.animationDelay = `${Math.random() * 6}s`;
        star.style.animationDuration = `${Math.random() * 3 + 2.5}s`;
        container.appendChild(star);
    }
}

// ==========================================
// Drifting Constellation Background (Canvas)
// ==========================================
function setupDriftingConstellations() {
    const canvas = document.getElementById("constellation-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    let W, H;
    const constellations = [];
    const CONSTELLATION_COUNT = 6;

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = document.documentElement.scrollHeight;
    }

    window.addEventListener("resize", resize);
    resize();

    // Observe body height changes for scroll-length canvas
    const resizeObserver = new ResizeObserver(() => {
        H = canvas.height = document.documentElement.scrollHeight;
    });
    resizeObserver.observe(document.body);

    // Generate constellation patterns
    function createConstellation() {
        const starCount = Math.floor(Math.random() * 4) + 4; // 4–7 stars
        const cx = Math.random() * W;
        const cy = Math.random() * H;
        const spread = 60 + Math.random() * 80;

        const stars = [];
        for (let i = 0; i < starCount; i++) {
            stars.push({
                ox: (Math.random() - 0.5) * spread * 2,
                oy: (Math.random() - 0.5) * spread * 2,
                r: Math.random() * 1.5 + 0.8,
            });
        }

        // Create edges (connect nearby stars)
        const edges = [];
        for (let i = 0; i < stars.length; i++) {
            for (let j = i + 1; j < stars.length; j++) {
                const dx = stars[i].ox - stars[j].ox;
                const dy = stars[i].oy - stars[j].oy;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < spread * 1.5) {
                    edges.push([i, j]);
                }
            }
        }

        return {
            x: cx,
            y: cy,
            vx: (Math.random() - 0.5) * 0.15,
            vy: (Math.random() - 0.5) * 0.1 - 0.03, // slight upward drift
            stars: stars,
            edges: edges,
            opacity: Math.random() * 0.3 + 0.1,
            rotation: Math.random() * Math.PI * 2,
            rotationSpeed: (Math.random() - 0.5) * 0.0003,
        };
    }

    for (let i = 0; i < CONSTELLATION_COUNT; i++) {
        constellations.push(createConstellation());
    }

    function getThemeColors() {
        const style = getComputedStyle(document.documentElement);
        return {
            starColor: style.getPropertyValue("--canvas-star-color").trim() || "rgba(188, 213, 255, 0.6)",
            lineColor: style.getPropertyValue("--canvas-line-color").trim() || "rgba(188, 213, 255, 0.08)",
        };
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);
        const colors = getThemeColors();

        constellations.forEach(c => {
            // Update position
            c.x += c.vx;
            c.y += c.vy;
            c.rotation += c.rotationSpeed;

            // Wrap around
            if (c.x < -200) c.x = W + 200;
            if (c.x > W + 200) c.x = -200;
            if (c.y < -200) c.y = H + 200;
            if (c.y > H + 200) c.y = -200;

            const cos = Math.cos(c.rotation);
            const sin = Math.sin(c.rotation);

            // Calculate rotated positions
            const positions = c.stars.map(s => ({
                x: c.x + s.ox * cos - s.oy * sin,
                y: c.y + s.ox * sin + s.oy * cos,
                r: s.r,
            }));

            // Draw edges
            ctx.strokeStyle = colors.lineColor;
            ctx.lineWidth = 0.8;
            c.edges.forEach(([a, b]) => {
                ctx.beginPath();
                ctx.moveTo(positions[a].x, positions[a].y);
                ctx.lineTo(positions[b].x, positions[b].y);
                ctx.globalAlpha = c.opacity * 0.6;
                ctx.stroke();
            });

            // Draw stars
            positions.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = colors.starColor;
                ctx.globalAlpha = c.opacity;
                ctx.fill();
            });

            ctx.globalAlpha = 1;
        });

        requestAnimationFrame(draw);
    }

    draw();
}

// ==========================================
// Theme Toggle
// ==========================================
function setupThemeToggle() {
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;

    // Load saved preference
    const saved = localStorage.getItem("lyra_landing_theme");
    if (saved) {
        document.documentElement.setAttribute("data-theme", saved);
    }

    toggle.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("lyra_landing_theme", next);
    });
}

// ==========================================
// Expandable Feature Orbs
// ==========================================
function setupExpandableFeatures() {
    const orbs = document.querySelectorAll(".feature-orb");

    orbs.forEach(orb => {
        orb.addEventListener("click", () => {
            const isExpanded = orb.classList.contains("expanded");

            // Collapse all
            orbs.forEach(o => o.classList.remove("expanded"));

            // Toggle this one
            if (!isExpanded) {
                orb.classList.add("expanded");

                // Trigger inner animations
                const energyFill = orb.querySelector(".energy-fill");
                if (energyFill) {
                    energyFill.classList.remove("animate");
                    void energyFill.offsetWidth; // reflow
                    energyFill.classList.add("animate");
                }

                const bars = orb.querySelectorAll(".chart-bar");
                bars.forEach(bar => {
                    bar.classList.remove("animate");
                    void bar.offsetWidth;
                    bar.classList.add("animate");
                });
            }
        });
    });
}

// ==========================================
// Scroll Reveals
// ==========================================
function setupScrollReveals() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("visible");
            }
        });
    }, { threshold: 0.15, rootMargin: "0px 0px -50px 0px" });

    document.querySelectorAll(".reveal-item").forEach(el => observer.observe(el));
}

// ==========================================
// Stat Counter Animation
// ==========================================
function setupStatCounters() {
    const counters = document.querySelectorAll(".stat-number[data-target]");

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.counted) {
                entry.target.dataset.counted = "true";
                animateCounter(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(c => observer.observe(c));
}

function animateCounter(el) {
    const target = parseInt(el.dataset.target);
    const duration = 1200;
    const start = performance.now();

    function tick(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased);
        if (progress < 1) {
            requestAnimationFrame(tick);
        } else {
            el.textContent = target;
        }
    }

    requestAnimationFrame(tick);
}

// ==========================================
// Demo Animations (Energy bar, Chart bars, Radar)
// ==========================================
function setupDemoAnimations() {
    // Radar chart data animation
    const radarData = document.querySelector(".radar-data");
    if (radarData) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    radarData.classList.add("animate");
                }
            });
        }, { threshold: 0.3 });
        observer.observe(radarData);
    }
}
