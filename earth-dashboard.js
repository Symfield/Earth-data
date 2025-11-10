// Phase-Coherent Earth Dashboard
// Interactive 3D visualization using Symfield mathematics

class PhaseCoherentEarth {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.earth = null;
        this.animationId = null;
        
        // Phase-coherent parameters
        this.semiAxes = { a: 1.0501, b: 0.9823, c: 0.9477 };
        this.fuzzyWeights = [0.95, 0.87, 0.72, 0.58, 0.41];
        this.biasVector = { x: 0.15, y: 0.02, z: 0.08 };
        this.fci = 1.96;
        this.itci = 2.31;
        
        // Time tracking
        this.time = 0;
        this.lastUpdate = Date.now();
        
        this.init();
        this.animate();
        this.startDataUpdates();
    }
    
    init() {
        const canvas = document.getElementById('earth-canvas');
        const container = canvas.parentElement;
        
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x000011);
        
        // Camera setup
        this.camera = new THREE.PerspectiveCamera(
            75, 
            container.clientWidth / container.clientHeight, 
            0.1, 
            1000
        );
        this.camera.position.z = 3;
        
        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: canvas,
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Create Earth with dynamic triaxial geometry
        this.createEarth();
        this.createMemoryRings();
        this.createBiasIndicator();
        this.createLighting();
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
        
        // Mouse controls
        this.setupControls();
    }
    
    createEarth() {
        // Create triaxial ellipsoid geometry
        const geometry = new THREE.SphereGeometry(1, 64, 32);
        
        // Apply phase-coherent deformation
        const positions = geometry.attributes.position;
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i);
            const y = positions.getY(i);
            const z = positions.getZ(i);
            
            // Scale by current semi-axes
            positions.setX(i, x * this.semiAxes.a);
            positions.setY(i, y * this.semiAxes.b);
            positions.setZ(i, z * this.semiAxes.c);
        }
        
        // Create Earth material with coherence field visualization
        const material = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                biasVector: { value: new THREE.Vector3(this.biasVector.x, this.biasVector.y, this.biasVector.z) },
                fci: { value: this.fci },
                earthTexture: { value: this.createEarthTexture() }
            },
            vertexShader: `
                uniform float time;
                uniform vec3 biasVector;
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying vec2 vUv;
                
                void main() {
                    vPosition = position;
                    vNormal = normal;
                    vUv = uv;
                    
                    // Apply subtle phase oscillations
                    vec3 newPosition = position;
                    float phaseOffset = dot(position, biasVector) * sin(time * 0.5) * 0.02;
                    newPosition += normal * phaseOffset;
                    
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 biasVector;
                uniform float fci;
                uniform sampler2D earthTexture;
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying vec2 vUv;
                
                void main() {
                    // Base Earth color
                    vec3 earthColor = texture2D(earthTexture, vUv).rgb;
                    
                    // Coherence field visualization
                    float coherence = fci / 2.0;
                    float biasInfluence = dot(normalize(vPosition), normalize(biasVector));
                    
                    // Color modulation based on phase coherence
                    vec3 phaseColor = mix(
                        vec3(1.0, 0.4, 0.2), // Orange for high coherence
                        vec3(0.2, 0.6, 1.0), // Blue for low coherence
                        coherence
                    );
                    
                    // Blend with bias influence
                    earthColor = mix(earthColor, phaseColor, abs(biasInfluence) * 0.3);
                    
                    // Add subtle pulsing based on time
                    float pulse = sin(time * 2.0) * 0.1 + 0.9;
                    earthColor *= pulse;
                    
                    gl_FragColor = vec4(earthColor, 1.0);
                }
            `
        });
        
        this.earth = new THREE.Mesh(geometry, material);
        this.earth.castShadow = true;
        this.earth.receiveShadow = true;
        this.scene.add(this.earth);
    }
    
    createEarthTexture() {
        // Create a procedural Earth-like texture
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        // Create gradient for basic Earth appearance
        const gradient = ctx.createLinearGradient(0, 0, 256, 128);
        gradient.addColorStop(0, '#1e3a8a');    // Deep ocean
        gradient.addColorStop(0.3, '#3b82f6');  // Ocean
        gradient.addColorStop(0.5, '#22c55e');  // Land
        gradient.addColorStop(0.7, '#eab308');  // Desert
        gradient.addColorStop(1, '#f3f4f6');    // Ice
        
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 256, 128);
        
        // Add some noise for continents
        const imageData = ctx.getImageData(0, 0, 256, 128);
        for (let i = 0; i < imageData.data.length; i += 4) {
            const noise = Math.random() * 0.3;
            imageData.data[i] *= (1 + noise);     // R
            imageData.data[i + 1] *= (1 + noise); // G
            imageData.data[i + 2] *= (1 + noise); // B
        }
        ctx.putImageData(imageData, 0, 0);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        return texture;
    }
    
    createMemoryRings() {
        this.memoryRings = [];
        
        for (let i = 0; i < this.fuzzyWeights.length; i++) {
            const ringGeometry = new THREE.RingGeometry(
                1.3 + i * 0.15, 
                1.35 + i * 0.15, 
                64
            );
            
            const ringMaterial = new THREE.MeshBasicMaterial({
                color: new THREE.Color().setHSL(0.6 - i * 0.1, 0.8, 0.5),
                transparent: true,
                opacity: this.fuzzyWeights[i] * 0.6,
                side: THREE.DoubleSide
            });
            
            const ring = new THREE.Mesh(ringGeometry, ringMaterial);
            ring.rotation.x = Math.PI / 2;
            this.memoryRings.push(ring);
            this.scene.add(ring);
        }
    }
    
    createBiasIndicator() {
        // Create arrow showing bias vector direction
        const arrowGeometry = new THREE.ConeGeometry(0.05, 0.3, 8);
        const arrowMaterial = new THREE.MeshBasicMaterial({ color: 0xff6b35 });
        this.biasArrow = new THREE.Mesh(arrowGeometry, arrowMaterial);
        
        // Position arrow based on bias vector
        const length = Math.sqrt(
            this.biasVector.x ** 2 + 
            this.biasVector.y ** 2 + 
            this.biasVector.z ** 2
        );
        
        this.biasArrow.position.set(
            this.biasVector.x * 2,
            this.biasVector.y * 2,
            this.biasVector.z * 2
        );
        
        this.biasArrow.lookAt(
            this.biasVector.x * 3,
            this.biasVector.y * 3,
            this.biasVector.z * 3
        );
        
        this.scene.add(this.biasArrow);
    }
    
    createLighting() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
        this.scene.add(ambientLight);
        
        // Directional light (sun)
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(5, 5, 5);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        // Point light for phase field illumination
        const pointLight = new THREE.PointLight(0xff6b35, 0.5, 100);
        pointLight.position.set(-2, 2, 2);
        this.scene.add(pointLight);
    }
    
    setupControls() {
        let mouseDown = false;
        let mouseX = 0;
        let mouseY = 0;
        
        const canvas = this.renderer.domElement;
        
        canvas.addEventListener('mousedown', (event) => {
            mouseDown = true;
            mouseX = event.clientX;
            mouseY = event.clientY;
        });
        
        canvas.addEventListener('mousemove', (event) => {
            if (!mouseDown) return;
            
            const deltaX = event.clientX - mouseX;
            const deltaY = event.clientY - mouseY;
            
            this.earth.rotation.y += deltaX * 0.01;
            this.earth.rotation.x += deltaY * 0.01;
            
            mouseX = event.clientX;
            mouseY = event.clientY;
        });
        
        canvas.addEventListener('mouseup', () => {
            mouseDown = false;
        });
        
        canvas.addEventListener('wheel', (event) => {
            this.camera.position.z += event.deltaY * 0.001;
            this.camera.position.z = Math.max(1.5, Math.min(5, this.camera.position.z));
        });
    }
    
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        
        const now = Date.now();
        const delta = (now - this.lastUpdate) / 1000;
        this.time += delta;
        this.lastUpdate = now;
        
        // Update Earth shader uniforms
        if (this.earth.material.uniforms) {
            this.earth.material.uniforms.time.value = this.time;
            this.earth.material.uniforms.biasVector.value.set(
                this.biasVector.x,
                this.biasVector.y,
                this.biasVector.z
            );
            this.earth.material.uniforms.fci.value = this.fci;
        }
        
        // Rotate Earth slowly
        if (this.earth) {
            this.earth.rotation.y += 0.002;
        }
        
        // Update memory rings
        this.memoryRings.forEach((ring, index) => {
            ring.rotation.z += 0.001 * (index + 1);
            ring.material.opacity = this.fuzzyWeights[index] * 0.6;
        });
        
        // Update bias arrow
        if (this.biasArrow) {
            this.biasArrow.rotation.y = this.time * 0.5;
        }
        
        this.renderer.render(this.scene, this.camera);
    }
    
    startDataUpdates() {
        // Simulate real data updates every 30 seconds
        setInterval(() => this.updatePhaseCoherentData(), 30000);
        
        // Initial update
        this.updatePhaseCoherentData();
    }
    
    updatePhaseCoherentData() {
        // Simulate ⧖-preserving updates with realistic variations
        const strainVariation = (Math.random() - 0.5) * 0.001;
        
        // Update semi-axes with small phase coherent changes
        this.semiAxes.a += strainVariation;
        this.semiAxes.b += strainVariation * 0.8;
        this.semiAxes.c += strainVariation * 0.6;
        
        // Update bias vector
        this.biasVector.x += (Math.random() - 0.5) * 0.01;
        this.biasVector.y += (Math.random() - 0.5) * 0.005;
        this.biasVector.z += (Math.random() - 0.5) * 0.007;
        
        // Update coherence indices
        this.fci = Math.max(1.5, Math.min(2.5, this.fci + (Math.random() - 0.5) * 0.1));
        this.itci = Math.max(1.8, Math.min(2.8, this.itci + (Math.random() - 0.5) * 0.1));
        
        // Update fuzzy weights with decay
        this.fuzzyWeights = this.fuzzyWeights.map((weight, index) => {
            const decay = Math.exp(-0.02 * (index + 1));
            return Math.max(0.1, Math.min(1.0, weight * decay + Math.random() * 0.1));
        });
        
        // Update UI elements
        this.updateUI();
        
        // Update 3D geometry
        this.updateEarthGeometry();
    }
    
    updateUI() {
        // Update metric displays
        document.getElementById('fci-value').textContent = this.fci.toFixed(2);
        document.getElementById('itci-value').textContent = this.itci.toFixed(2);
        
        // Update bias indicator
        const magnitude = Math.sqrt(
            this.biasVector.x ** 2 + 
            this.biasVector.y ** 2 + 
            this.biasVector.z ** 2
        );
        const angle = Math.atan2(this.biasVector.y, this.biasVector.x) * 180 / Math.PI;
        
        document.getElementById('bias-magnitude').textContent = 
            `Magnitude: ${magnitude.toFixed(3)} | Direction: ${angle.toFixed(1)}°`;
        
        // Update memory rings
        const rings = document.querySelectorAll('.coherence-fill');
        rings.forEach((ring, index) => {
            if (this.fuzzyWeights[index] !== undefined) {
                ring.style.width = `${this.fuzzyWeights[index] * 100}%`;
            }
        });
        
        // Update semi-axes display
        const semiAxesDiv = document.querySelector('.controls-panel').lastElementChild;
        if (semiAxesDiv) {
            const spans = semiAxesDiv.querySelectorAll('span[style*="color"]');
            if (spans.length >= 3) {
                spans[0].textContent = this.semiAxes.a.toFixed(4);
                spans[1].textContent = this.semiAxes.b.toFixed(4);
                spans[2].textContent = this.semiAxes.c.toFixed(4);
            }
        }
        
        // Update timestamp
        document.getElementById('last-update').textContent = 
            new Date().toLocaleString('en-US', { 
                timeZone: 'UTC',
                year: 'numeric',
                month: 'long', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            }) + ' UTC';
    }
    
    updateEarthGeometry() {
        if (!this.earth) return;
        
        const geometry = this.earth.geometry;
        const positions = geometry.attributes.position;
        
        // Update positions based on new semi-axes
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i) / this.semiAxes.a; // Normalize
            const y = positions.getY(i) / this.semiAxes.b;
            const z = positions.getZ(i) / this.semiAxes.c;
            
            // Reapply current semi-axes
            positions.setX(i, x * this.semiAxes.a);
            positions.setY(i, y * this.semiAxes.b);
            positions.setZ(i, z * this.semiAxes.c);
        }
        
        positions.needsUpdate = true;
        geometry.computeVertexNormals();
    }
    
    onWindowResize() {
        const container = this.renderer.domElement.parentElement;
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        
        this.renderer.setSize(width, height);
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        if (this.renderer) {
            this.renderer.dispose();
        }
        
        window.removeEventListener('resize', this.onWindowResize);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.phaseCoherentEarth = new PhaseCoherentEarth();
    
    // Add some console info for developers
    console.log('🌍 Phase-Coherent Earth Monitor Initialized');
    console.log('⧖ Using Symfield Non-Collapse Mathematics');
    console.log('📡 Real-time field coherence tracking active');
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PhaseCoherentEarth;
}