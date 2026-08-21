import { useEffect, useRef } from "react";
import * as THREE from "three";

/** A small decorative rotating wireframe/glass icosahedron rendered with
 * plain Three.js (no react-three-fiber) so this component owns its own
 * canvas sizing outright, rather than depending on a resize-observer
 * abstraction that can silently fail to size the canvas in some browser
 * environments. Purely decorative -- any failure here (no WebGL, etc.)
 * is caught and the component just renders nothing. */
export default function Scene3D({ className = "" }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let renderer;
    let frameId;
    let resizeObserver;
    let disposed = false;

    try {
      const width = container.clientWidth || 380;
      const height = container.clientHeight || 380;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
      camera.position.set(0, 0, 5);

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.setSize(width, height);
      container.appendChild(renderer.domElement);

      scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
      keyLight.position.set(3, 3, 3);
      scene.add(keyLight);
      const rimLight = new THREE.DirectionalLight(0x7c3aed, 0.4);
      rimLight.position.set(-3, -2, -3);
      scene.add(rimLight);

      const geometry = new THREE.IcosahedronGeometry(1.4, 0);
      const solid = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({ color: 0x2563eb, metalness: 0.4, roughness: 0.15, transparent: true, opacity: 0.85 }),
      );
      scene.add(solid);

      const wireframe = new THREE.Mesh(
        geometry,
        new THREE.MeshBasicMaterial({ color: 0x93c5fd, wireframe: true, transparent: true, opacity: 0.35 }),
      );
      wireframe.scale.setScalar(1.35);
      scene.add(wireframe);

      const animate = () => {
        if (disposed) return;
        solid.rotation.x += 0.0025;
        solid.rotation.y += 0.0037;
        wireframe.rotation.x -= 0.0013;
        wireframe.rotation.y -= 0.002;
        renderer.render(scene, camera);
        frameId = requestAnimationFrame(animate);
      };
      animate();

      const handleResize = () => {
        const w = container.clientWidth || width;
        const h = container.clientHeight || height;
        renderer.setSize(w, h);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(container);
      } else {
        window.addEventListener("resize", handleResize);
      }

      return () => {
        disposed = true;
        if (frameId) cancelAnimationFrame(frameId);
        if (resizeObserver) resizeObserver.disconnect();
        else window.removeEventListener("resize", handleResize);
        geometry.dispose();
        solid.material.dispose();
        wireframe.material.dispose();
        renderer.dispose();
        if (renderer.domElement.parentNode === container) {
          container.removeChild(renderer.domElement);
        }
      };
    } catch {
      // WebGL unavailable or failed to initialize -- this is purely
      // decorative, so fail silently rather than break the page.
      return undefined;
    }
  }, []);

  return <div ref={containerRef} className={className} aria-hidden="true" />;
}
