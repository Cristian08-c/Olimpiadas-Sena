/**
 * Sistema de partículas para efectos visuales de fondo
 * Proporciona animaciones de partículas conectadas con líneas
 */
export default class ParticleSystem {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.warn(`Canvas con ID "${canvasId}" no encontrado`);
      return;
    }

    this.ctx = this.canvas.getContext("2d");
    this.particles = [];

    // Configuración por defecto
    this.config = {
      numParticles: 50,
      maxDistance: 100,
      particleSpeed: 0.5,
      particleSize: 2,
      particleColor: options.particleColor || "rgba(57, 169, 0, 0.6)",
      lineColor: options.lineColor || "rgba(57, 169, 0, 0.2)",
      ...options,
    };

    this.init();
    this.animate();
    this.handleResize();
  }

  init() {
    this.resizeCanvas();
    this.createParticles();
  }

  resizeCanvas() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  createParticles() {
    this.particles = [];
    for (let i = 0; i < this.config.numParticles; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * this.config.particleSpeed,
        vy: (Math.random() - 0.5) * this.config.particleSpeed,
        size: Math.random() * this.config.particleSize + 1,
      });
    }
  }

  updateParticles() {
    this.particles.forEach((particle) => {
      particle.x += particle.vx;
      particle.y += particle.vy;

      // Rebote en los bordes
      if (particle.x < 0 || particle.x > this.canvas.width) {
        particle.vx *= -1;
      }
      if (particle.y < 0 || particle.y > this.canvas.height) {
        particle.vy *= -1;
      }

      // Mantener dentro de los límites
      particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
      particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
    });
  }

  drawParticles() {
    this.ctx.fillStyle = this.config.particleColor;
    this.particles.forEach((particle) => {
      this.ctx.beginPath();
      this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
      this.ctx.fill();
    });
  }

  drawConnections() {
    this.ctx.strokeStyle = this.config.lineColor;
    this.ctx.lineWidth = 1;

    for (let i = 0; i < this.particles.length; i++) {
      for (let j = i + 1; j < this.particles.length; j++) {
        const dx = this.particles[i].x - this.particles[j].x;
        const dy = this.particles[i].y - this.particles[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < this.config.maxDistance) {
          this.ctx.beginPath();
          this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
          this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
          this.ctx.stroke();
        }
      }
    }
  }

  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.updateParticles();
    this.drawConnections();
    this.drawParticles();

    requestAnimationFrame(() => this.animate());
  }

  handleResize() {
    window.addEventListener("resize", () => {
      this.resizeCanvas();
      this.createParticles();
    });
  }
}
