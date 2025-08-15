document.addEventListener('DOMContentLoaded', () => {
    // --- Global Variables ---
    const graphContainer = document.getElementById('graph-container');
    const loadingOverlay = document.getElementById('loading');
    const loadingTextEl = document.querySelector('#loading .loading-text');
    const themeSwitcher = document.getElementById('theme-switcher');

    // Detail Panel Elements
    const detailPanel = document.getElementById('detail-panel');
    const detailTitleEl = document.getElementById('detail-title');
    const detailMetaEl = document.getElementById('detail-meta');
    
    let Graph;
    let graphData = { "nodes": [], "links": [] };
    let currentTheme = 'dark';

    const API_BASE = window.location.origin;
    const GRAPH_DATA_URL = `${API_BASE}/api/graph-data`;

    let hands, camera;
    let draggedNode = null;
    let lastDragMovement = { x: 0, y: 0, z: 0 };
    let pointingNode = null; // Track pointed node
    let pointingStartTime = 0;
    const pointingDuration = 1500; // 1.5 seconds to trigger click
    
    let handHistory = [];
    let pinchHistory = [];
    let smoothingFrames = 3; 
    let currentPinchState = false;
    let pinchStartPos = null;
    
    let pinchDistanceThreshold = 0.08; 
    let dragSensitivity = 1000; 
    let handTrackingConfidence = 0;

    // Gesture state variables with smoothing
    let zoomState = { active: false, lastDistance: 0, smoothedDelta: 0 };
    let rotationState = { active: false, lastControlPos: null, smoothedDelta: { x: 0, y: 0 } };
    const zoomSensitivity = 800; // Increased sensitivity
    const rotationSensitivity = 4; // Increased sensitivity
    const smoothingFactor = 0.3; // Higher = more responsive

    const nodeColors = {
        'todo': '#ff6b6b', 
        'in_progress': '#feca57', 
        'done': '#48ca89', 
        'blocked': '#ff9ff3', 
        'default': '#54a0ff'
    };

    // --- Helper to update loading status ---
    function updateLoadingStatus(message, isError = false) {
        if (loadingTextEl) {
            loadingTextEl.textContent = message;
            loadingTextEl.style.color = isError ? 'var(--error-color)' : 'var(--accent-color)';
        }
    }

    // --- Main Initialization ---
    async function initializeApp() {
        try {
            updateLoadingStatus('Fetching graph data...');
            await loadGraphData();
            
            updateLoadingStatus('Assembling 3D scene...');
            setupGraph();
            
            updateLoadingStatus('Initializing gesture tracking...');
            await setupGestureTracking();
            
            updateLoadingStatus('Finalizing UI...');
            setupThemeSwitcher();

            updateLoadingStatus('Done!');
            if (loadingOverlay) {
                loadingOverlay.style.opacity = '0';
                setTimeout(() => { loadingOverlay.style.display = 'none'; }, 500);
            }
        } catch (error) {
            console.error('Initialization error:', error);
            updateLoadingStatus(`Error: ${error.message}`, true);
        }
    }

    // --- Theme Switcher Setup ---
    function setupThemeSwitcher() {
        if (!themeSwitcher) return;
        
        const sunIcon = document.getElementById('theme-icon-sun');
        const moonIcon = document.getElementById('theme-icon-moon');
        
        themeSwitcher.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            
            if (document.body.classList.contains('light-theme')) {
                currentTheme = 'light';
                if (Graph) Graph.backgroundColor('#f5f5f7');
                if (sunIcon) sunIcon.style.display = 'none';
                if (moonIcon) moonIcon.style.display = 'block';
            } else {
                currentTheme = 'dark';
                if (Graph) Graph.backgroundColor('#0a0a0a');
                if (sunIcon) sunIcon.style.display = 'block';
                if (moonIcon) moonIcon.style.display = 'none';
            }

            // Update node text colors for theme change
            if (Graph && Graph.graphData()) {
                Graph.graphData().nodes.forEach(node => {
                    if (node.__threeObj) {
                        const sprite = node.__threeObj.children.find(child => child.isSprite);
                        if (sprite && sprite.material && sprite.material.map) {
                            const canvas = sprite.material.map.image;
                            if (canvas && canvas.getContext) {
                                const ctx = canvas.getContext('2d');
                                const fontSize = 32;
                                const text = node.title || 'Node';
                                ctx.clearRect(0, 0, canvas.width, canvas.height);
                                ctx.font = `bold ${fontSize}px Sans-serif`;
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                ctx.fillStyle = (currentTheme === 'dark') ? '#ffffff' : '#000000';
                                ctx.fillText(text, canvas.width / 2, canvas.height / 2);
                                sprite.material.map.needsUpdate = true;
                            }
                        }
                    }
                });
            }
        });
    }

    // --- Data Handling ---
    async function loadGraphData() {
        try {
            const response = await fetch(GRAPH_DATA_URL);
            if (!response.ok) throw new Error(`API Error: ${response.status}`);
            graphData = await response.json();
            
            // Validate graph data structure
            if (!graphData || typeof graphData !== 'object') {
                throw new Error('Invalid graph data format');
            }
            if (!Array.isArray(graphData.nodes)) {
                graphData.nodes = [];
            }
            if (!Array.isArray(graphData.links)) {
                graphData.links = [];
            }
        } catch (error) {
            console.error('Failed to load graph data:', error);
            graphData = { 
                nodes: [{ id: 'error', title: 'Error Loading Data', status: 'blocked' }], 
                links: [] 
            };
        }
    }

    // --- 3D Graph Setup ---
    function setupGraph() {
        if (!graphContainer) {
            console.error('Graph container not found');
            return;
        }

        Graph = ForceGraph3D()(graphContainer)
            .graphData(graphData)
            .d3AlphaMin(0.02) // Keep simulation running
            .d3AlphaDecay(0.005) // Slower decay for gentle movement
            .d3VelocityDecay(0.8) // Higher friction
            .backgroundColor('#0a0a0a')
            .nodeLabel('title')
            .nodeThreeObject(node => {
                const group = new THREE.Group();
                
                // Create bubble geometry
                const bubbleGeometry = new THREE.SphereGeometry(18, 32, 32);
                const bubbleMaterial = new THREE.MeshPhongMaterial({
                    color: nodeColors[node.status] || nodeColors.default,
                    transparent: true, 
                    opacity: 0.8,
                    shininess: 90, 
                    specular: 0xefefef
                });
                group.add(new THREE.Mesh(bubbleGeometry, bubbleMaterial));
                
                // Create text sprite
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const fontSize = 32;
                const text = node.title || 'Node';
                
                ctx.font = `bold ${fontSize}px Sans-serif`;
                const textWidth = ctx.measureText(text).width;
                canvas.width = Math.max(textWidth + 16, 64); // Minimum width
                canvas.height = fontSize + 8;
                
                // Redraw with proper canvas size
                ctx.font = `bold ${fontSize}px Sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = (currentTheme === 'dark') ? '#ffffff' : '#000000';
                ctx.fillText(text, canvas.width / 2, canvas.height / 2);
                
                const texture = new THREE.CanvasTexture(canvas);
                const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ 
                    map: texture, 
                    transparent: true 
                }));
                
                const spriteHeight = 12;
                sprite.scale.set((spriteHeight * canvas.width) / canvas.height, spriteHeight, 1.0);
                sprite.position.set(0, 28, 0);
                group.add(sprite);
                
                return group;
            })
            .linkWidth(1.5)
            .linkCurvature(0)
            .linkDirectionalParticles(0)
            .linkColor(() => (currentTheme === 'dark' ? 'rgba(0, 212, 255, 0.8)' : 'rgba(0, 113, 227, 0.7)'))
            .onNodeClick(node => {
                const distance = 250;
                const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0);
                Graph.cameraPosition(
                    { 
                        x: (node.x || 0) * distRatio, 
                        y: (node.y || 0) * distRatio, 
                        z: (node.z || 0) * distRatio 
                    },
                    node, 
                    1000
                );
                showDetailPanel(node);
            });
        
        // Configure force simulation for very gentle movement
        if (Graph.d3Force) {
            Graph.d3Force('link').distance(60);
            Graph.d3Force('charge').strength(-10); // Much gentler repulsion
            Graph.d3Force('center').strength(0.02); // Weaker centering
        }

        // Keep simulation alive with periodic reheat
        setInterval(() => {
            if (Graph && Graph.d3Force && !draggedNode) {
                const alpha = Graph.d3Force('simulation') ? Graph.d3Force('simulation').alpha() : 0;
                if (alpha < 0.01) { // Lower threshold for gentler reheating
                    Graph.d3ReheatSimulation && Graph.d3ReheatSimulation();
                }
            }
        }, 8000); // Every 8 seconds for slower rhythm

        // Add lighting and milky way stars
        const scene = Graph.scene();
        if (scene) {
            scene.add(new THREE.AmbientLight(0xcccccc, 0.9));
            const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
            dirLight.position.set(100, 100, 100);
            scene.add(dirLight);
            
            // Add milky way effect
            addMilkyWayStars(scene);
        }
    }

    // Add small dots for milky way effect
    function addMilkyWayStars(scene) {
        const starGeometry = new THREE.BufferGeometry();
        const starCount = 2000;
        const positions = new Float32Array(starCount * 3);
        
        for (let i = 0; i < starCount * 3; i++) {
            positions[i] = (Math.random() - 0.5) * 4000; // Spread across large area
        }
        
        starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        const starMaterial = new THREE.PointsMaterial({
            color: 0xffffff,
            size: 1,
            transparent: true,
            opacity: 0.3
        });
        
        const stars = new THREE.Points(starGeometry, starMaterial);
        scene.add(stars);
    }

    // --- Gesture Tracking & Handlers ---
    async function setupGestureTracking() {
        if (!('mediaDevices' in navigator) || !navigator.mediaDevices.getUserMedia) {
            console.warn('Camera not supported');
            disableGestureFeatures();
            return;
        }
        
        try {
            updateLoadingStatus('Awaiting camera permission...');
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: { ideal: 1280 }, 
                    height: { ideal: 720 }, 
                    frameRate: { ideal: 60 } 
                } 
            });
            
            updateLoadingStatus('Initializing hand tracking...');
            const video = document.querySelector('.input_video');
            const canvas = document.getElementById('hand-overlay');
            const webcamBackground = document.getElementById('webcam-background');
            
            if (canvas) {
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight;
            }
            
            // Initialize MediaPipe Hands
            if (typeof Hands !== 'undefined') {
                hands = new Hands({ 
                    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}` 
                });
                hands.onResults(onHandResults);
                hands.setOptions({ 
                    maxNumHands: 2, 
                    modelComplexity: 0, 
                    minDetectionConfidence: 0.8, 
                    minTrackingConfidence: 0.8 
                });
            }
            
            // Initialize camera
            if (typeof Camera !== 'undefined' && video) {
                camera = new Camera(video, { 
                    onFrame: async () => { 
                        if (hands) await hands.send({ image: video }); 
                    }, 
                    width: 1280, 
                    height: 720, 
                    fps: 60 
                });
                
                if (webcamBackground) webcamBackground.srcObject = stream;
                video.srcObject = stream;
                camera.start();
            } else {
                disableGestureFeatures();
            }
        } catch (error) {
            console.error('Camera access denied or not available.', error);
            disableGestureFeatures();
            throw new Error("Camera permission was denied. Please allow camera access and refresh.");
        }
    }
    
    function disableGestureFeatures() {
        console.log("Gesture features disabled.");
        const gestureUI = document.getElementById('gesture-ui');
        const handOverlay = document.getElementById('hand-overlay');
        const webcamBackground = document.getElementById('webcam-background');
        
        if (gestureUI) gestureUI.remove();
        if (handOverlay) handOverlay.remove();
        if (webcamBackground) webcamBackground.remove();
    }
    
    // --- Hand gesture analysis ---
    function getHandOpenness(hand) {
        if (!hand || hand.length < 21) return 0;
        
        const wrist = hand[0];
        const fingerTops = [hand[8], hand[12], hand[16], hand[20]];
        let totalDistance = 0;
        
        for (const finger of fingerTops) {
            if (finger && wrist) {
                totalDistance += Math.hypot(finger.x - wrist.x, finger.y - wrist.y);
            }
        }
        
        return totalDistance;
    }

    function onHandResults(results) {
        const canvas = document.getElementById('hand-overlay');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const numHands = results.multiHandLandmarks?.length || 0;
        
        if (numHands === 2) {
            handleTwoHands(results);
        } else if (numHands === 1) {
            handleOneHand(results);
        } else {
            handleNoHands();
        }
    }

    function handleNoHands() {
        clearHandHistory();
        updateGestureStatus('Inactive', 'status-off');
        updateGestureUI('gesture-action', 'Show your hand to camera');
        updateGestureUI('gesture-confidence', '0%');
        
        if (draggedNode) releaseDraggedNode();
        currentPinchState = false;
        zoomState.active = false;
        rotationState.active = false;
    }

    function handleOneHand(results) {
        zoomState.active = false;
        rotationState.active = false;
        
        const primaryHand = results.multiHandLandmarks[0];
        const handedness = results.multiHandedness?.[0]?.label || 'Unknown';
        
        updateGestureStatus(`Active (${handedness})`, 'status-on');
        addToHandHistory(primaryHand);
        
        const smoothedHand = getSmoothedHand();
        if (smoothedHand) {
            processGestures(smoothedHand);
            drawEnhancedHand(smoothedHand, currentPinchState);
        }
    }

    function handleTwoHands(results) {
        clearHandHistory();
        if (draggedNode) releaseDraggedNode();
        
        const hand1 = results.multiHandLandmarks[0];
        const hand2 = results.multiHandLandmarks[1];
        
        drawEnhancedHand(hand1, false);
        drawEnhancedHand(hand2, false);
        
        // Robust gesture routing based on hand openness difference
        const openness1 = getHandOpenness(hand1);
        const openness2 = getHandOpenness(hand2);
        const opennessDifferenceThreshold = 0.15;

        const isRotationGesture = Math.abs(openness1 - openness2) > opennessDifferenceThreshold;

        // Reset the state of the gesture that is NOT active
        if (isRotationGesture) {
            zoomState.active = false;
        } else {
            rotationState.active = false;
        }

        // Route to the appropriate handler
        if (isRotationGesture || rotationState.active) {
            handleRotation(hand1, hand2, openness1, openness2);
        } else {
            handleZoom(hand1, hand2);
        }
    }

    function handleRotation(hand1, hand2, openness1, openness2) {
        const opennessDifferenceThreshold = 0.12; // More sensitive

        // If the hands become too similar, exit the rotation gesture
        if (Math.abs(openness1 - openness2) < opennessDifferenceThreshold) {
            rotationState.active = false;
            rotationState.smoothedDelta = { x: 0, y: 0 }; // Reset smoothing
            updateGestureStatus('Active (Two Hands)', 'status-on');
            updateGestureUI('gesture-action', 'Make one hand a fist to rotate');
            return;
        }

        // The hand with smaller "openness" score is the fist (control hand)
        const controlHand = (openness1 < openness2) ? hand1 : hand2;
        const controlHandPos = { x: controlHand[9].x, y: controlHand[9].y }; 

        if (!rotationState.active) {
            rotationState.active = true;
            rotationState.lastControlPos = controlHandPos;
            rotationState.smoothedDelta = { x: 0, y: 0 };
            return; // Skip first frame to avoid jump
        }

        const rawDeltaX = controlHandPos.x - rotationState.lastControlPos.x;
        const rawDeltaY = controlHandPos.y - rotationState.lastControlPos.y;

        // Apply exponential smoothing
        rotationState.smoothedDelta.x = rotationState.smoothedDelta.x * (1 - smoothingFactor) + rawDeltaX * smoothingFactor;
        rotationState.smoothedDelta.y = rotationState.smoothedDelta.y * (1 - smoothingFactor) + rawDeltaY * smoothingFactor;

        // Apply rotation with smoothed values
        if (Graph && Graph.camera && (Math.abs(rotationState.smoothedDelta.x) > 0.001 || Math.abs(rotationState.smoothedDelta.y) > 0.001)) {
            const camera = Graph.camera();
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(camera.position);
            
            // Apply smooth rotation
            spherical.theta -= rotationState.smoothedDelta.x * rotationSensitivity;
            spherical.phi += rotationState.smoothedDelta.y * rotationSensitivity;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));
            
            camera.position.setFromSpherical(spherical);
            camera.lookAt(0, 0, 0);
        }

        rotationState.lastControlPos = controlHandPos;
        
        updateGestureStatus('Active (Rotation)', 'status-on');
        updateGestureUI('gesture-action', 'Move fist to rotate');
        updateGestureUI('gesture-confidence', 'Rotating');
    }

    function handleZoom(hand1, hand2) {
        const wrist1 = hand1[0];
        const wrist2 = hand2[0];
        const distance = Math.hypot(wrist1.x - wrist2.x, wrist1.y - wrist2.y);
        
        updateGestureStatus('Active (Two Hands)', 'status-on');

        if (!zoomState.active) {
            zoomState.active = true;
            zoomState.lastDistance = distance;
            zoomState.smoothedDelta = 0;
            updateGestureUI('gesture-action', 'Move hands to zoom');
            return; // Skip first frame
        }

        const rawDelta = distance - zoomState.lastDistance;
        
        // Apply exponential smoothing
        zoomState.smoothedDelta = zoomState.smoothedDelta * (1 - smoothingFactor) + rawDelta * smoothingFactor;
        
        if (Graph && Graph.camera && Math.abs(zoomState.smoothedDelta) > 0.002) {
            const cam = Graph.camera();
            const camPos = cam.position.clone();
            const direction = camPos.clone().normalize();
            
            camPos.add(direction.multiplyScalar(zoomState.smoothedDelta * zoomSensitivity));
            
            // Smooth zoom limits
            const minDist = 50;
            const maxDist = 2000;
            const currentDist = camPos.length();
            
            if (currentDist < minDist) camPos.normalize().multiplyScalar(minDist);
            else if (currentDist > maxDist) camPos.normalize().multiplyScalar(maxDist);
            
            cam.position.copy(camPos);
        }
        
        zoomState.lastDistance = distance;
        updateGestureUI('gesture-confidence', 'Zooming');
    }

    function addToHandHistory(hand) {
        handHistory.push({ landmarks: hand, timestamp: Date.now() });
        if (handHistory.length > smoothingFrames) {
            handHistory.shift();
        }
    }

    function clearHandHistory() { 
        handHistory = []; 
        pinchHistory = []; 
    }

    function getSmoothedHand() {
        if (handHistory.length < 2) {
            return handHistory[0]?.landmarks;
        }
        
        const smoothedLandmarks = [];
        for (let i = 0; i < 21; i++) {
            let x = 0, y = 0, z = 0;
            handHistory.forEach(frame => {
                if (frame.landmarks[i]) {
                    x += frame.landmarks[i].x; 
                    y += frame.landmarks[i].y; 
                    z += frame.landmarks[i].z;
                }
            });
            smoothedLandmarks.push({ 
                x: x / handHistory.length, 
                y: y / handHistory.length, 
                z: z / handHistory.length 
            });
        }
        return smoothedLandmarks;
    }

    function processGestures(hand) {
        const pinchData = calculatePinchData(hand);
        const pointData = calculatePointData(hand);
        const isPinching = pinchData.distance < pinchDistanceThreshold;
        
        // Handle pointing gesture
        handlePointingGesture(pointData);
        
        pinchHistory.push({ isPinching, ...pinchData });
        if (pinchHistory.length > smoothingFrames) {
            pinchHistory.shift();
        }
        
        const shouldBePinching = pinchHistory.slice(-3).filter(p => p.isPinching).length >= 2;
        
        if (shouldBePinching && !currentPinchState) {
            startPinchGesture(pinchData);
        } else if (shouldBePinching && currentPinchState) {
            continuePinchGesture(pinchData);
        } else if (!shouldBePinching && currentPinchState) {
            stopPinchGesture();
        } else {
            updateGestureUI('gesture-action', 'Make pinch gesture or point at node');
            updateGestureUI('gesture-confidence', `${Math.round(pinchData.confidence)}%`);
        }
    }

    function calculatePointData(hand) {
        const indexTip = hand[8];
        const indexPip = hand[6];
        const middleTip = hand[12];
        const ringTip = hand[16];
        const pinkyTip = hand[20];
        
        // Check if index is extended and others are curled
        const indexExtended = indexTip.y < indexPip.y;
        const othersCurled = middleTip.y > hand[10].y && ringTip.y > hand[14].y && pinkyTip.y > hand[18].y;
        const isPointing = indexExtended && othersCurled;
        
        return {
            position: indexTip,
            isPointing: isPointing,
            confidence: isPointing ? 100 : 0
        };
    }

    function handlePointingGesture(pointData) {
        if (!pointData.isPointing) {
            pointingNode = null;
            pointingStartTime = 0;
            return;
        }
        
        const targetNode = findNodeAtPosition(pointData.position);
        
        if (targetNode) {
            if (pointingNode === targetNode) {
                // Still pointing at same node
                const elapsed = Date.now() - pointingStartTime;
                const progress = Math.min(elapsed / pointingDuration, 1);
                
                updateGestureUI('gesture-action', `Pointing at: ${targetNode.title?.substring(0, 15)}... ${Math.round(progress * 100)}%`);
                
                if (progress >= 1) {
                    // Trigger click!
                    clickNode(targetNode);
                    pointingNode = null;
                    pointingStartTime = 0;
                }
            } else {
                // New node pointed at
                pointingNode = targetNode;
                pointingStartTime = Date.now();
            }
        } else {
            pointingNode = null;
            pointingStartTime = 0;
        }
    }

    function findNodeAtPosition(fingerPos) {
        if (!Graph || !graphData.nodes) return null;
        
        const canvas = document.getElementById('hand-overlay');
        if (!canvas) return null;
        
        let closestNode = null;
        let minDistance = Infinity;
        
        graphData.nodes.forEach(node => {
            if (node.x === undefined || node.y === undefined || node.z === undefined) return;
            
            try {
                const screenPos = Graph.graph2ScreenCoords(node.x, node.y, node.z);
                if (!screenPos) return;
                
                const distance = Math.hypot(
                    screenPos.x - fingerPos.x * canvas.width,
                    screenPos.y - fingerPos.y * canvas.height
                );
                
                if (distance < 150 && distance < minDistance) { // Generous pointing area
                    minDistance = distance;
                    closestNode = node;
                }
            } catch (e) {
                console.warn('Error calculating node distance:', e);
            }
        });
        
        return closestNode;
    }

    function clickNode(node) {
        // Same as node click functionality
        const distance = 250;
        const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0);
        Graph.cameraPosition(
            { 
                x: (node.x || 0) * distRatio, 
                y: (node.y || 0) * distRatio, 
                z: (node.z || 0) * distRatio 
            },
            node, 
            1000
        );
        showDetailPanel(node);
        updateGestureUI('gesture-action', `Clicked: ${node.title?.substring(0, 20)}`);
    }

    function calculatePinchData(hand) {
        const thumb = hand[4];
        const index = hand[8];
        const distance = Math.hypot(
            thumb.x - index.x, 
            thumb.y - index.y, 
            (thumb.z - index.z) * 0.5
        );
        const position = { 
            x: (thumb.x + index.x) / 2, 
            y: (thumb.y + index.y) / 2, 
            z: (thumb.z + index.z) / 2 
        };
        const confidence = Math.max(0, Math.min(100, 
            ((0.1 - distance) / (0.1 - pinchDistanceThreshold)) * 100
        ));
        return { distance, position, confidence };
    }

    function startPinchGesture(pinchData) {
        currentPinchState = true;
        pinchStartPos = pinchData.position;
        findClosestNodeToPinch(pinchData.position);
        
        const actionText = draggedNode ? 
            `Grabbed: ${draggedNode.title?.substring(0, 20)}` : 'Pinching';
        updateGestureUI('gesture-action', actionText);
        updateGestureUI('gesture-confidence', `${Math.round(pinchData.confidence)}%`);
    }

    function continuePinchGesture(pinchData) {
        if (!draggedNode) return;
        
        handlePinchDrag(pinchData.position);
        updateGestureUI('gesture-confidence', `${Math.round(pinchData.confidence)}%`);
    }

    function stopPinchGesture() {
        currentPinchState = false;
        if (draggedNode) {
            updateGestureUI('gesture-action', `Released: ${draggedNode.title?.substring(0, 20)}`);
            setTimeout(() => { 
                if (!currentPinchState) releaseDraggedNode(); 
            }, 500);
        }
        pinchStartPos = null;
    }

    function findClosestNodeToPinch(pinchPos) {
        if (!Graph || !graphData.nodes) return;
        
        let closestNode = null;
        let minDistance = Infinity;
        const canvas = document.getElementById('hand-overlay');
        if (!canvas) return;

        graphData.nodes.forEach(node => {
            if (node.x === undefined || node.y === undefined || node.z === undefined) return;
            
            try {
                const screenPos = Graph.graph2ScreenCoords(node.x, node.y, node.z);
                if (!screenPos) return;
                
                const distance = Math.hypot(
                    screenPos.x - pinchPos.x * canvas.width, 
                    screenPos.y - pinchPos.y * canvas.height
                );
                
                if (distance < minDistance) {
                    const camera = Graph.camera();
                    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
                    const edgePoint3D = { 
                        x: node.x + right.x * 18, 
                        y: node.y + right.y * 18, 
                        z: node.z + right.z * 18 
                    };
                    const edgeScreenPos = Graph.graph2ScreenCoords(
                        edgePoint3D.x, edgePoint3D.y, edgePoint3D.z
                    );
                    if (!edgeScreenPos) return;
                    
                    const screenRadius = Math.hypot(
                        screenPos.x - edgeScreenPos.x, 
                        screenPos.y - edgeScreenPos.y
                    );
                    
                    if (distance < screenRadius + 120) {
                        minDistance = distance;
                        closestNode = node;
                    }
                }
            } catch (e) {
                console.warn('Error calculating node distance:', e);
            }
        });
        
        if (closestNode) {
            draggedNode = closestNode;
            draggedNode.fx = closestNode.x; 
            draggedNode.fy = closestNode.y; 
            draggedNode.fz = closestNode.z;
        }
    }

    function handlePinchDrag(currentPos) {
        if (!draggedNode || !pinchStartPos) return;
        
        const delta = { 
            x: currentPos.x - pinchStartPos.x, 
            y: currentPos.y - pinchStartPos.y 
        };
        
        const camera = Graph.camera();
        const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
        
        const moveScale = camera.position.distanceTo(
            new THREE.Vector3(draggedNode.x, draggedNode.y, draggedNode.z)
        ) * 0.001;
        
        const moveDir = right.multiplyScalar(delta.x).add(up.multiplyScalar(-delta.y));
        moveDir.multiplyScalar(dragSensitivity * moveScale);
        
        lastDragMovement = { x: moveDir.x, y: moveDir.y, z: moveDir.z };
        
        draggedNode.fx += moveDir.x; 
        draggedNode.fy += moveDir.y; 
        draggedNode.fz += moveDir.z;
        
        pinchStartPos = { ...currentPos };
        
        if (Graph.refresh) Graph.refresh();
        
        updateGestureUI('gesture-action', `Dragging: ${draggedNode.title?.substring(0, 20)}`);
    }

    function releaseDraggedNode() {
        if (draggedNode) {
            delete draggedNode.fx; 
            delete draggedNode.fy; 
            delete draggedNode.fz;
            
            const bounceFactor = 2.5; // Much bouncier!
            draggedNode.vx = lastDragMovement.x * bounceFactor;
            draggedNode.vy = lastDragMovement.y * bounceFactor;
            draggedNode.vz = lastDragMovement.z * bounceFactor;
            
            // Restart the simulation to keep gentle movement
            if (Graph.d3ReheatSimulation) Graph.d3ReheatSimulation();
            if (Graph.d3Force) {
                Graph.d3Force('center').strength(0.02); // Keep center force active
            }
            
            draggedNode = null;
            lastDragMovement = { x: 0, y: 0, z: 0 };
            
            setTimeout(() => { 
                if (!currentPinchState) {
                    updateGestureUI('gesture-action', 'Make pinch gesture'); 
                }
            }, 1000);
        }
        pinchStartPos = null;
    }

    function drawEnhancedHand(hand, isPinching) {
        const canvas = document.getElementById('hand-overlay');
        if (!hand || !canvas) return;
        
        const ctx = canvas.getContext('2d');
        const { width, height } = canvas;
        
        const baseColor = isPinching ? '#00ff88' : '#00d4ff';
        const accentColor = isPinching ? '#ff0066' : '#ff6b35';
        
        ctx.lineWidth = isPinching ? 4 : 3;
        ctx.strokeStyle = baseColor;
        ctx.fillStyle = accentColor;
        
        // Hand connection patterns
        const connections = [
            [0, 1, 2, 3, 4],      // Thumb
            [0, 5, 6, 7, 8],      // Index finger
            [0, 9, 10, 11, 12],   // Middle finger
            [0, 13, 14, 15, 16],  // Ring finger
            [0, 17, 18, 19, 20],  // Pinky
            [5, 9, 13, 17, 5]     // Hand outline
        ];
        
        connections.forEach(conn => {
            ctx.beginPath();
            for (let i = 0; i < conn.length; i++) {
                const p = hand[conn[i]];
                if (p) {
                    if (i === 0) {
                        ctx.moveTo(p.x * width, p.y * height);
                    } else {
                        ctx.lineTo(p.x * width, p.y * height);
                    }
                }
            }
            ctx.stroke();
        });
    }

    function updateGestureStatus(text, className) {
        const el = document.getElementById('gesture-status');
        if (!el) return;
        
        el.className = className;
        el.innerHTML = `<span class="status-indicator"></span>${text}`;
    }

    function updateGestureUI(elementId, text) {
        const el = document.getElementById(elementId);
        if (el) el.textContent = text;
    }

    function showDetailPanel(node) {
        if (!detailPanel || !detailTitleEl || !detailMetaEl) return;
        
        detailPanel.classList.add('visible');
        detailTitleEl.textContent = node.title || 'No Title';
        detailMetaEl.textContent = `ID: ${node.id}`;
        
        const authorEl = document.getElementById('detail-author');
        const statusEl = document.getElementById('detail-status');
        const createdEl = document.getElementById('detail-created');
        const filenameEl = document.getElementById('detail-filename');
        const descriptionEl = document.getElementById('detail-description');
        
        if (authorEl) authorEl.textContent = node.author || 'N/A';
        if (statusEl) {
            statusEl.innerHTML = `<span class="status-badge" style="background:${nodeColors[node.status] || nodeColors.default}">${node.status || 'Unknown'}</span>`;
        }
        if (createdEl) createdEl.textContent = node.created_at || 'N/A';
        if (filenameEl) filenameEl.textContent = node.filename || 'N/A';
        if (descriptionEl) descriptionEl.textContent = node.description || 'No description provided.';
    }
    
    // Global function to hide detail panel
    window.hideDetailPanel = function() { 
        if (detailPanel) detailPanel.classList.remove('visible'); 
    };
    
    // Window resize handler
    window.addEventListener('resize', () => {
        const canvas = document.getElementById('hand-overlay');
        if (canvas) { 
            canvas.width = window.innerWidth; 
            canvas.height = window.innerHeight; 
        }
        if (Graph && Graph.width && Graph.height) {
            Graph.width(window.innerWidth).height(window.innerHeight);
        }
    });
    
    // Start the application
    initializeApp();
});