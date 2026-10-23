/*
EXPLICACIÓN:
Se ha extraído la lógica de las partículas a su propio módulo.
MALA PRÁCTICA DETECTADA (original): El código de partículas estaba duplicado y era difícil de configurar.
CORRECCIÓN: Se convierte en una clase ParticleSystem reutilizable y configurable.
Ahora se puede importar en cualquier script y crear un nuevo sistema de partículas
con diferentes colores, cantidad, etc., sin tocar el código de la clase.
Esto sigue el principio de Separación de Responsabilidades.
*/
export default class ParticleSystem {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`Canvas con ID "${canvasId}" no encontrado.`);
      return;
    }
    this.ctx = this.canvas.getContext("2d");
    this.particles = [];

    // Se fusionan las opciones por defecto con las proporcionadas por el usuario
    this.config = {
      particleCount: 80,
      particleColor: "rgba(57, 169, 0, 0.5)",
      lineColor: "rgba(57, 169, 0, 0.1)",
      ...options,
    };

    // Se bindea 'this' para que no pierda el contexto en requestAnimationFrame
    this.animate = this.animate.bind(this);

    this.init();
    this.animate();

    window.addEventListener("resize", () => this.init(), { passive: true });
  }

  init() {
    // Se ajusta el canvas al tamaño de su contenedor padre.
    this.canvas.width = this.canvas.parentElement.offsetWidth;
    this.canvas.height = this.canvas.parentElement.offsetHeight;

    this.particles = [];
    for (let i = 0; i < this.config.particleCount; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        radius: Math.random() * 2 + 1,
      });
    }
  }

  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.particles.forEach((p1, i) => {
      p1.x += p1.vx;
      p1.y += p1.vy;

      if (p1.x < 0) p1.x = this.canvas.width;
      if (p1.x > this.canvas.width) p1.x = 0;
      if (p1.y < 0) p1.y = this.canvas.height;
      if (p1.y > this.canvas.height) p1.y = 0;

      this.ctx.beginPath();
      this.ctx.arc(p1.x, p1.y, p1.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = this.config.particleColor;
      this.ctx.fill();

      for (let j = i + 1; j < this.particles.length; j++) {
        const p2 = this.particles[j];
        const distance = Math.hypot(p1.x - p2.x, p1.y - p2.y);

        if (distance < 120) {
          this.ctx.beginPath();
          this.ctx.moveTo(p1.x, p1.y);
          this.ctx.lineTo(p2.x, p2.y);
          this.ctx.strokeStyle = this.config.lineColor;
          this.ctx.lineWidth = 1 - distance / 120;
          this.ctx.stroke();
        }
      }
    });

    requestAnimationFrame(this.animate);
  }
}
