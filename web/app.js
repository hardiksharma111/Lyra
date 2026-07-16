/* ==========================================
   Lyra Premium Web Interface - App Logic
   ========================================== */

document.addEventListener("DOMContentLoaded", () => {
    // State management
    const state = {
        mood: "casual",
        debug: false,
        isRecording: false,
        recognition: null,
        activeSession: null,
        sessions: {}, // { id: { title: "", messages: [...] } }
        
        // Settings State
        settings: {
            voiceName: "",
            movementMode: "both", // 'drag' | 'wander' | 'both'
            voiceRate: 1.0,
            speechEnabled: true
        },
        
        // Avatar Wandering Coordinates
        isDragging: false,
        wanderX: 0,
        wanderY: 0,
        targetX: null,
        targetY: null,
        wanderSpeed: 0.9, // pixels per frame (slow and subtle)
        voices: []
    };

    // DOM Elements
    const elements = {
        messagesArea: document.getElementById("chat-messages"),
        chatInput: document.getElementById("chat-input"),
        btnSend: document.getElementById("btn-send"),
        btnMic: document.getElementById("btn-mic"),
        lyraAvatar: document.getElementById("lyra-avatar"),
        modelIndicator: document.getElementById("model-indicator"),
        debugStateText: document.getElementById("debug-state"),
        btnSuggestions: document.getElementById("btn-suggestions"),
        btnErrors: document.getElementById("btn-errors"),
        btnDebug: document.getElementById("btn-debug"),
        debugActionsPane: document.getElementById("debug-actions-pane"),
        modalOverlay: document.getElementById("modal-container"),
        modalTitle: document.getElementById("modal-title"),
        modalBody: document.getElementById("modal-body"),
        btnCloseModal: document.getElementById("btn-close-modal"),
        btnNewChat: document.getElementById("btn-new-chat"),
        chatHistoryList: document.getElementById("chat-history-list"),
        welcomeView: document.getElementById("welcome-view"),
        btnSettings: document.getElementById("btn-settings")
    };

    // Initialize Page
    init();

    function init() {
        // Setup text area auto-grow
        elements.chatInput.addEventListener("input", autoGrowInput);

        // Send message event listeners
        elements.btnSend.addEventListener("click", sendMessage);
        elements.chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Mic/Speech recognition setup
        setupSpeechRecognition();
        elements.btnMic.addEventListener("click", toggleVoiceInput);

        // Sidebar actions
        elements.btnNewChat.addEventListener("click", startNewChat);
        elements.btnDebug.addEventListener("click", toggleDebugMode);
        elements.btnSuggestions.addEventListener("click", fetchSuggestions);
        elements.btnErrors.addEventListener("click", fetchErrors);
        elements.btnSettings.addEventListener("click", showSettingsPanel);

        // Modal close listeners
        elements.btnCloseModal.addEventListener("click", hideModal);
        elements.modalOverlay.addEventListener("click", (e) => {
            if (e.target === elements.modalOverlay) hideModal();
        });

        // Quick prompts click listener
        document.querySelectorAll(".prompt-card").forEach(card => {
            card.addEventListener("click", () => {
                const prompt = card.getAttribute("data-prompt");
                elements.chatInput.value = prompt;
                autoGrowInput();
                sendMessage();
            });
        });

        // Load settings from localStorage
        loadSettings();

        // Load voices dynamically
        setupVoiceSynthesis();

        // Set up draggable floating avatar
        setupDraggableAvatar();

        // Start wandering loop for avatar
        initWanderCoordinates();
        requestAnimationFrame(avatarWanderLoop);

        // Load sessions from local storage
        loadSessions();

        // Initial status load
        updateSystemStatus();
        setInterval(updateSystemStatus, 15000);

        elements.chatInput.focus();
    }

    // Input height adjustments
    function autoGrowInput() {
        elements.chatInput.style.height = "auto";
        elements.chatInput.style.height = (elements.chatInput.scrollHeight - 16) + "px";
    }

    // Append a message to the chat display
    function appendMessage(sender, text, save = true) {
        // Hide welcome view if first message
        if (elements.welcomeView && !elements.welcomeView.classList.contains("hidden")) {
            elements.welcomeView.classList.add("hidden");
            elements.messagesArea.classList.remove("hidden");
        }

        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}-msg`;
        
        const p = document.createElement("p");
        p.textContent = text;
        msgDiv.appendChild(p);
        
        elements.messagesArea.appendChild(msgDiv);
        elements.messagesArea.scrollTop = elements.messagesArea.scrollHeight;
        
        removeTypingIndicator();

        if (save && state.activeSession) {
            state.sessions[state.activeSession].messages.push({ sender, text });
            saveSessions();
            updateHistorySidebar();
        }
    }

    // Typing indicator
    function showTypingIndicator() {
        if (document.getElementById("typing-indicator")) return;
        
        // Hide welcome view if showing
        if (elements.welcomeView && !elements.welcomeView.classList.contains("hidden")) {
            elements.welcomeView.classList.add("hidden");
            elements.messagesArea.classList.remove("hidden");
        }

        const typingDiv = document.createElement("div");
        typingDiv.id = "typing-indicator";
        typingDiv.className = "message agent-msg";
        
        const p = document.createElement("p");
        p.innerHTML = '<span class="loading-shimmer" style="display:inline-block; width: 40px; height: 14px; vertical-align: middle;"></span>';
        typingDiv.appendChild(p);
        
        elements.messagesArea.appendChild(typingDiv);
        elements.messagesArea.scrollTop = elements.messagesArea.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById("typing-indicator");
        if (indicator) indicator.remove();
    }

    // API: Chat message submission
    async function sendMessage() {
        const text = elements.chatInput.value.trim();
        if (!text) return;

        // Create new session if none is active
        if (!state.activeSession) {
            createNewSession(text.length > 25 ? text.substring(0, 25) + "..." : text);
        }

        // Reset input area
        elements.chatInput.value = "";
        elements.chatInput.style.height = "auto";

        // Append user prompt
        appendMessage("user", text);
        showTypingIndicator();

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();
            
            if (data.status === "ok") {
                appendMessage("agent", data.response);
                
                // If backend returns mood/tone, update the orb styling
                if (data.mood) {
                    setOrbMood(data.mood);
                }
                
                // Trigger customized speech synthesis
                if (data.speak) {
                    speakText(data.response);
                }
            } else {
                appendMessage("agent", `Error: ${data.error || "failed to communicate with Lyra core."}`);
            }
        } catch (error) {
            appendMessage("agent", "Could not reach Lyra web server. Make sure the server script is running.");
            console.error("Chat error:", error);
        }
    }

    // Set Avatar Mood Classes
    function setOrbMood(mood) {
        const validMoods = ["casual", "focused", "concerned", "alert", "curious", "playful"];
        if (!validMoods.includes(mood)) mood = "casual";

        // Remove other classes
        validMoods.forEach(m => elements.lyraAvatar.classList.remove(m));
        
        // Add new class
        elements.lyraAvatar.classList.add(mood);
        state.mood = mood;
    }

    // Interactive Orb Greet
    function playOrbGreeting() {
        const greetings = {
            casual: "Hey. What's on your mind?",
            focused: "Ready to get things done. Let's execute.",
            concerned: "Take it easy. I'm right here.",
            alert: "Systems checked. Standing by.",
            curious: "Fascinating. What are we exploring?",
            playful: "Just checking in. Need something fun?"
        };
        
        const greet = greetings[state.mood] || greetings.casual;
        appendMessage("agent", greet);
        speakText(greet);
    }

    // Speech Customization Handler
    function speakText(text) {
        if (!state.settings.speechEnabled || !('speechSynthesis' in window)) return;

        window.speechSynthesis.cancel(); // Cancel current audio
        
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Configure voice selection
        if (state.settings.voiceName) {
            const voice = state.voices.find(v => v.name === state.settings.voiceName);
            if (voice) utterance.voice = voice;
        }
        
        // Configure speech rate speed
        utterance.rate = state.settings.voiceRate;
        utterance.pitch = 1.0;

        // Visual animations hooks
        utterance.onstart = () => {
            elements.lyraAvatar.classList.add("speaking");
        };

        utterance.onend = () => {
            elements.lyraAvatar.classList.remove("speaking");
        };

        utterance.onerror = () => {
            elements.lyraAvatar.classList.remove("speaking");
        };

        window.speechSynthesis.speak(utterance);
    }

    // Speech Synthesis initialization
    function setupVoiceSynthesis() {
        if (!('speechSynthesis' in window)) return;

        const loadVoices = () => {
            // Retrieve English and native voices
            state.voices = window.speechSynthesis.getVoices()
                .filter(v => v.lang.startsWith("en") || v.lang.startsWith("en-"));
        };

        loadVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = loadVoices;
        }
    }

    // Render & handle settings panel
    function showSettingsPanel() {
        // Build settings form dynamically
        let voiceOptions = '<option value="">(Default System Voice)</option>';
        state.voices.forEach(v => {
            const isSelected = v.name === state.settings.voiceName ? "selected" : "";
            const isFemale = v.name.toLowerCase().includes("zira") || v.name.toLowerCase().includes("hazel") || v.name.toLowerCase().includes("google") || v.name.toLowerCase().includes("samantha") || v.name.toLowerCase().includes("female");
            const genderLabel = isFemale ? "Female" : "Male/Unknown";
            voiceOptions += `<option value="${v.name}" ${isSelected}>${v.name} (${genderLabel})</option>`;
        });

        const settingsHtml = `
            <div class="settings-form">
                <div class="settings-group">
                    <label><i class="fa-solid fa-user-gear"></i> Choose Voice Tone</label>
                    <select id="settings-voice" class="settings-control">
                        ${voiceOptions}
                    </select>
                </div>
                <div class="settings-group">
                    <label><i class="fa-solid fa-wand-magic-sparkles"></i> Orb Motion Pattern</label>
                    <select id="settings-avatar-mode" class="settings-control">
                        <option value="drag" ${state.settings.movementMode === "drag" ? "selected" : ""}>Draggable Only</option>
                        <option value="wander" ${state.settings.movementMode === "wander" ? "selected" : ""}>Autonomous Wandering</option>
                        <option value="both" ${state.settings.movementMode === "both" ? "selected" : ""}>Draggable & Wandering</option>
                    </select>
                </div>
                <div class="settings-group">
                    <label><i class="fa-solid fa-gauge"></i> Speaking Rate: <span id="rate-val">${state.settings.voiceRate.toFixed(1)}x</span></label>
                    <input type="range" id="settings-voice-rate" class="settings-slider" min="0.5" max="1.6" step="0.1" value="${state.settings.voiceRate}">
                </div>
                <div class="settings-row">
                    <label><i class="fa-solid fa-volume-high"></i> Enable Voice Output</label>
                    <label class="switch">
                        <input type="checkbox" id="settings-speech-enabled" ${state.settings.speechEnabled ? "checked" : ""}>
                        <span class="slider-toggle"></span>
                    </label>
                </div>
            </div>
        `;

        showModal("Lyra Settings", settingsHtml);

        // Attach change listeners to modal elements
        const voiceSelect = document.getElementById("settings-voice");
        const modeSelect = document.getElementById("settings-avatar-mode");
        const rateSlider = document.getElementById("settings-voice-rate");
        const speechCheckbox = document.getElementById("settings-speech-enabled");

        voiceSelect.addEventListener("change", (e) => {
            state.settings.voiceName = e.target.value;
            saveSettings();
            // Test voice immediately
            speakText("Selected voice tone.");
        });

        modeSelect.addEventListener("change", (e) => {
            state.settings.movementMode = e.target.value;
            saveSettings();
            if (state.settings.movementMode === "drag") {
                // Return to bottom-right corner smoothly
                elements.lyraAvatar.style.transition = "all 0.8s cubic-bezier(0.25, 1, 0.5, 1)";
                elements.lyraAvatar.style.left = "";
                elements.lyraAvatar.style.top = "";
                elements.lyraAvatar.style.right = "30px";
                elements.lyraAvatar.style.bottom = "30px";
                setTimeout(() => {
                    elements.lyraAvatar.style.transition = "box-shadow 0.5s ease";
                }, 800);
            }
        });

        rateSlider.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            state.settings.voiceRate = val;
            document.getElementById("rate-val").textContent = val.toFixed(1) + "x";
            saveSettings();
        });

        speechCheckbox.addEventListener("change", (e) => {
            state.settings.speechEnabled = e.target.checked;
            saveSettings();
        });
    }

    // Local Storage helpers
    function saveSettings() {
        localStorage.setItem("lyra_settings", JSON.stringify(state.settings));
    }

    function loadSettings() {
        try {
            const saved = localStorage.getItem("lyra_settings");
            if (saved) {
                state.settings = { ...state.settings, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.error("Failed to load settings:", e);
        }
    }

    // Fetch and update system status (minimalist)
    async function updateSystemStatus() {
        try {
            const response = await fetch("/api/status");
            const data = await response.json();
            
            if (data.status === "ok") {
                // Update debug status
                if (data.debug) {
                    elements.btnDebug.classList.add("active");
                    elements.debugStateText.textContent = "ON";
                    elements.debugActionsPane.classList.remove("hidden");
                } else {
                    elements.btnDebug.classList.remove("active");
                    elements.debugStateText.textContent = "OFF";
                    elements.debugActionsPane.classList.add("hidden");
                }
                state.debug = data.debug;

                if (data.mood) {
                    setOrbMood(data.mood);
                }
            }
        } catch (error) {
            console.error("Error loading status:", error);
        }
    }

    // Modal view helpers
    function showModal(title, htmlContent) {
        elements.modalTitle.textContent = title;
        elements.modalBody.innerHTML = htmlContent;
        elements.modalOverlay.classList.remove("hidden");
        elements.modalOverlay.offsetHeight; // force reflow
        elements.modalOverlay.classList.add("visible");
    }

    function hideModal() {
        elements.modalOverlay.classList.remove("visible");
        setTimeout(() => {
            elements.modalOverlay.classList.add("hidden");
        }, 300);
        // Clear any synthetic speaking tests on close
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    }

    // Fetch suggestions
    async function fetchSuggestions() {
        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: "suggestions" })
            });
            const data = await response.json();
            
            if (data.status === "ok") {
                let html = "";
                const items = data.response.split(" | ");
                
                if (items.length === 1 && items[0].includes("No suggestions")) {
                    html = `<p style="text-align:center; padding: 20px 0;">${items[0]}</p>`;
                } else {
                    items.forEach(item => {
                        const idx = item.indexOf(":");
                        const title = idx !== -1 ? item.substring(0, idx) : "Suggestion";
                        const desc = idx !== -1 ? item.substring(idx + 1) : item;
                        
                        html += `
                            <div class="modal-item">
                                <div class="modal-item-title"><i class="fa-solid fa-lightbulb" style="color:#f6d365;"></i> ${title.trim()}</div>
                                <div>${desc.trim()}</div>
                            </div>
                        `;
                    });
                }
                
                showModal("Improvement Suggestions", html);
            }
        } catch (error) {
            showModal("Error", "<p>Failed to retrieve suggestions from backend.</p>");
        }
    }

    // Fetch errors
    async function fetchErrors() {
        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: "errors" })
            });
            const data = await response.json();
            
            if (data.status === "ok") {
                let html = "";
                const items = data.response.split(" | ");
                
                if (items.length === 1 && items[0].includes("No errors")) {
                    html = `<p style="text-align:center; padding: 20px 0;">${items[0]}</p>`;
                } else {
                    items.forEach(item => {
                        const tsMatch = item.match(/^\[(.*?)\]/);
                        const ts = tsMatch ? tsMatch[1] : "";
                        const rest = tsMatch ? item.substring(tsMatch[0].length) : item;
                        
                        const idx = rest.indexOf(":");
                        const component = idx !== -1 ? rest.substring(0, idx) : "Error";
                        const msg = idx !== -1 ? rest.substring(idx + 1) : rest;
                        
                        html += `
                            <div class="modal-item" style="border-left: 3px solid #ff0844;">
                                <div class="modal-item-title" style="display:flex; justify-content:space-between;">
                                    <span><i class="fa-solid fa-bug" style="color:#ff0844;"></i> ${component.trim()}</span>
                                    <span style="font-size:0.75rem; color:var(--text-muted); font-weight:normal;">${ts}</span>
                                </div>
                                <div style="margin-top: 4px; font-family: monospace; font-size:0.8rem; word-break: break-all;">${msg.trim()}</div>
                            </div>
                        `;
                    });
                }
                
                showModal("Error Log History", html);
            }
        } catch (error) {
            showModal("Error", "<p>Failed to retrieve errors from backend.</p>");
        }
    }

    // Toggle debug mode
    async function toggleDebugMode() {
        const cmd = state.debug ? "debug off" : "debug on";
        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: cmd })
            });
            const data = await response.json();
            
            if (data.status === "ok") {
                state.debug = !state.debug;
                if (state.debug) {
                    elements.btnDebug.classList.add("active");
                    elements.debugStateText.textContent = "ON";
                    elements.debugActionsPane.classList.remove("hidden");
                } else {
                    elements.btnDebug.classList.remove("active");
                    elements.debugStateText.textContent = "OFF";
                    elements.debugActionsPane.classList.add("hidden");
                }
            }
        } catch (error) {
            console.error("Error toggling debug mode:", error);
        }
    }

    // Speech Recognition Setup using Browser Web Speech API
    function setupSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            elements.btnMic.style.display = "none";
            return;
        }

        state.recognition = new SpeechRecognition();
        state.recognition.continuous = false;
        state.recognition.interimResults = false;
        state.recognition.lang = "en-US";

        state.recognition.onstart = () => {
            state.isRecording = true;
            elements.btnMic.innerHTML = '<i class="fa-solid fa-square" style="color:#ff0844;"></i>';
            elements.chatInput.placeholder = "Listening to your voice...";
            elements.btnMic.classList.add("recording");
        };

        state.recognition.onend = () => {
            state.isRecording = false;
            elements.btnMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
            elements.chatInput.placeholder = "Ask Lyra something...";
            elements.btnMic.classList.remove("recording");
        };

        state.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            elements.chatInput.value = transcript;
            autoGrowInput();
            
            // Auto send voice command after a small delay
            setTimeout(sendMessage, 800);
        };

        state.recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            state.isRecording = false;
            elements.btnMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
            elements.chatInput.placeholder = "Ask Lyra something...";
            elements.btnMic.classList.remove("recording");
        };
    }

    function toggleVoiceInput() {
        if (!state.recognition) return;

        if (state.isRecording) {
            state.recognition.stop();
        } else {
            // Cancel any current speaking greetings
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
            state.recognition.start();
        }
    }

    // ==========================================
    // Interactive Draggable Floating Avatar Orb
    // ==========================================
    function setupDraggableAvatar() {
        const orb = elements.lyraAvatar;
        let startX, startY;
        let displacementX = 0;
        let displacementY = 0;

        // Mouse Drag events
        orb.addEventListener("mousedown", dragStart);
        window.addEventListener("mousemove", dragMove);
        window.addEventListener("mouseup", dragEnd);

        // Touch drag events (Mobile)
        orb.addEventListener("touchstart", dragStart, { passive: true });
        window.addEventListener("touchmove", dragMove, { passive: false });
        window.addEventListener("touchend", dragEnd);

        function dragStart(e) {
            // Click only triggers if dragging doesn't occur
            state.isDragging = true;
            orb.style.transition = "none";
            orb.style.animationPlayState = "paused";

            const clientX = e.type === "touchstart" ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === "touchstart" ? e.touches[0].clientY : e.clientY;

            startX = clientX - state.wanderX;
            startY = clientY - state.wanderY;
            
            displacementX = 0;
            displacementY = 0;
        }

        function dragMove(e) {
            if (!state.isDragging) return;

            // Prevent scroll on mobile touch events
            if (e.type === "touchmove") {
                e.preventDefault();
            }

            const clientX = e.type === "touchmove" ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === "touchmove" ? e.touches[0].clientY : e.clientY;

            // Calculate new position relative to viewport
            let x = clientX - startX;
            let y = clientY - startY;

            // Clamp coordinates inside viewport bounds
            const rect = orb.getBoundingClientRect();
            const maxX = window.innerWidth - rect.width;
            const maxY = window.innerHeight - rect.height;

            x = Math.max(0, Math.min(x, maxX));
            y = Math.max(0, Math.min(y, maxY));

            // Track displacement
            displacementX = x - state.wanderX;
            displacementY = y - state.wanderY;

            // Update state coordinates
            state.wanderX = x;
            state.wanderY = y;

            // Apply style positions
            orb.style.left = x + "px";
            orb.style.top = y + "px";
            orb.style.right = "auto";
            orb.style.bottom = "auto";
        }

        function dragEnd(e) {
            if (!state.isDragging) return;
            state.isDragging = false;

            // Restore float animation
            orb.style.transition = "box-shadow 0.5s ease";
            orb.style.animationPlayState = "running";

            // If we wander, clear targets to start wandering from this spot
            state.targetX = null;
            state.targetY = null;

            const distanceMoved = Math.sqrt(displacementX * displacementX + displacementY * displacementY);

            // Tap gesture threshold (6px)
            if (distanceMoved < 6) {
                playOrbGreeting();
            }
        }
    }

    // Initialize wander coordinates to default bottom-right viewport location
    function initWanderCoordinates() {
        const orb = elements.lyraAvatar;
        const rect = orb.getBoundingClientRect();
        
        // Grab current computed styles (or default right/bottom location)
        state.wanderX = rect.left;
        state.wanderY = rect.top;
        
        // Make sure style matches coordinates
        orb.style.left = state.wanderX + "px";
        orb.style.top = state.wanderY + "px";
        orb.style.right = "auto";
        orb.style.bottom = "auto";
    }

    // Autonomous wandering animation loop
    function avatarWanderLoop() {
        const orb = elements.lyraAvatar;

        // Check if movement settings allow autonomous floating
        const mode = state.settings.movementMode;
        const shouldWander = (mode === "wander" || mode === "both");

        if (shouldWander && !state.isDragging) {
            const rect = orb.getBoundingClientRect();

            // Set new random coordinate target if none exists
            if (state.targetX === null || state.targetY === null) {
                const margin = 40;
                const maxX = window.innerWidth - rect.width - margin;
                const maxY = window.innerHeight - rect.height - margin;
                
                state.targetX = Math.random() * (maxX - margin) + margin;
                state.targetY = Math.random() * (maxY - margin) + margin;
            }

            // Calculate directional step
            const dx = state.targetX - state.wanderX;
            const dy = state.targetY - state.wanderY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 10) {
                // Arrived at target, clear so it picks a new one next frame
                state.targetX = null;
                state.targetY = null;
            } else {
                // Move towards target coordinates
                const step = Math.min(dist, state.wanderSpeed);
                state.wanderX += (dx / dist) * step;
                state.wanderY += (dy / dist) * step;

                // Apply style rules
                orb.style.left = state.wanderX + "px";
                orb.style.top = state.wanderY + "px";
                orb.style.right = "auto";
                orb.style.bottom = "auto";
            }
        } else if (!shouldWander && !state.isDragging && (orb.style.left === "" || orb.style.left === "0px")) {
            // Keep matching wanderX and wanderY to its bottom-right layout position
            const rect = orb.getBoundingClientRect();
            state.wanderX = rect.left;
            state.wanderY = rect.top;
        }

        requestAnimationFrame(avatarWanderLoop);
    }

    // ==========================================
    // Session History Sidebar Management
    // ==========================================
    function startNewChat() {
        if (state.activeSession && state.sessions[state.activeSession].messages.length === 0) {
            return;
        }

        // De-select active item
        document.querySelectorAll(".history-item").forEach(item => item.classList.remove("active"));
        
        state.activeSession = null;
        elements.messagesArea.innerHTML = "";
        elements.messagesArea.classList.add("hidden");
        elements.welcomeView.classList.remove("hidden");
        
        elements.chatInput.value = "";
        elements.chatInput.style.height = "auto";
        elements.chatInput.focus();
    }

    function createNewSession(title) {
        const id = "session_" + Date.now();
        state.sessions[id] = {
            title: title,
            messages: []
        };
        state.activeSession = id;
        saveSessions();
        updateHistorySidebar();
    }

    function selectSession(id) {
        if (!state.sessions[id]) return;
        state.activeSession = id;
        
        // Mark active in sidebar
        document.querySelectorAll(".history-item").forEach(item => {
            item.classList.remove("active");
            if (item.getAttribute("data-id") === id) {
                item.classList.add("active");
            }
        });

        // Render session dialogue messages
        elements.messagesArea.innerHTML = "";
        const messages = state.sessions[id].messages;

        if (messages.length === 0) {
            elements.welcomeView.classList.remove("hidden");
            elements.messagesArea.classList.add("hidden");
        } else {
            elements.welcomeView.classList.add("hidden");
            elements.messagesArea.classList.remove("hidden");
            
            messages.forEach(msg => {
                appendMessage(msg.sender, msg.text, false);
            });
        }
        
        elements.chatInput.focus();
    }

    function updateHistorySidebar() {
        elements.chatHistoryList.innerHTML = "";
        const sortedIds = Object.keys(state.sessions).sort((a, b) => b - a);

        if (sortedIds.length === 0) {
            elements.chatHistoryList.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding: 15px 0;">No past sessions</div>';
            return;
        }

        sortedIds.forEach(id => {
            const item = document.createElement("div");
            item.className = `history-item ${id === state.activeSession ? "active" : ""}`;
            item.setAttribute("data-id", id);
            item.innerHTML = `<i class="fa-solid fa-message"></i> ${state.sessions[id].title}`;
            
            item.addEventListener("click", () => selectSession(id));
            elements.chatHistoryList.appendChild(item);
        });
    }

    function saveSessions() {
        localStorage.setItem("lyra_chat_sessions", JSON.stringify(state.sessions));
    }

    function loadSessions() {
        try {
            const saved = localStorage.getItem("lyra_chat_sessions");
            if (saved) {
                state.sessions = JSON.parse(saved);
                updateHistorySidebar();
            }
        } catch (e) {
            console.error("Failed to load chat history:", e);
            state.sessions = {};
        }
    }
});
