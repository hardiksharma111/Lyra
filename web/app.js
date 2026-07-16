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
        activeView: "chat", // 'chat' | 'settings'
        
        // Settings State
        settings: {
            voiceName: "",
            movementMode: "both", // 'drag' | 'wander' | 'both'
            voiceRate: 1.0,
            speechEnabled: true,
            voiceVolume: 80 // 0 to 100
        },
        
        // Avatar Wandering Coordinates
        isDragging: false,
        wanderX: 0,
        wanderY: 0,
        targetX: null,
        targetY: null,
        wanderSpeed: 0.9,
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
        btnDebug: document.getElementById("btn-debug"),
        btnNewChat: document.getElementById("btn-new-chat"),
        btnSettings: document.getElementById("btn-settings"),
        chatHistoryList: document.getElementById("chat-history-list"),
        welcomeView: document.getElementById("welcome-view"),
        
        // View Panel Sections
        chatView: document.getElementById("chat-view"),
        settingsView: document.getElementById("settings-view"),
        
        // Settings Controls
        btnSpeechYes: document.getElementById("btn-speech-yes"),
        btnSpeechNo: document.getElementById("btn-speech-no"),
        volumeSettingsGroup: document.getElementById("volume-settings-group"),
        settingsVoiceVolume: document.getElementById("settings-voice-volume"),
        volumeVal: document.getElementById("volume-val"),
        volumeIcon: document.getElementById("volume-icon"),
        settingsVoice: document.getElementById("settings-voice"),
        settingsVoiceRate: document.getElementById("settings-voice-rate"),
        rateVal: document.getElementById("rate-val"),
        settingsAvatarMode: document.getElementById("settings-avatar-mode"),
        
        // Debug Dashboard Lists
        suggestionsList: document.getElementById("settings-suggestions-list"),
        errorsList: document.getElementById("settings-errors-list")
    };

    // Initialize Page
    init();

    function init() {
        // Generate Star constellation background
        generateStardustBackground();
        window.addEventListener("resize", generateStardustBackground);

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

        // Sidebar Navigation
        elements.btnNewChat.addEventListener("click", () => {
            startNewChat();
            showChatView();
        });
        elements.btnSettings.addEventListener("click", showSettingsView);
        elements.btnDebug.addEventListener("click", toggleDebugMode);

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

        // Initialize Speech voice synthesis engine
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

        // Set up Settings Page DOM bindings
        setupSettingsPageBindings();

        // Set up Command Palette
        setupCommandPalette();

        showChatView();
    }

    // Dynamic stardust generator
    function generateStardustBackground() {
        const container = document.getElementById("twinkling-stars");
        if (!container) return;
        
        container.innerHTML = "";
        const speeds = ["twinkle-slow", "twinkle-mid", "twinkle-fast"];
        
        // Fill viewport based on screen size
        const starCount = Math.floor((window.innerWidth * window.innerHeight) / 25000) + 15;
        
        for (let i = 0; i < starCount; i++) {
            const star = document.createElement("div");
            star.className = `star ${speeds[Math.floor(Math.random() * speeds.length)]}`;
            
            // Star size between 1px and 2.5px
            const size = (Math.random() * 1.5 + 1).toFixed(1);
            star.style.width = `${size}px`;
            star.style.height = `${size}px`;
            
            // Random location coordinates
            star.style.left = `${Math.random() * 100}%`;
            star.style.top = `${Math.random() * 100}%`;
            
            // Add timing variance to twinkling keyframes
            star.style.animationDelay = `${Math.random() * 6}s`;
            star.style.animationDuration = `${Math.random() * 3 + 2.5}s`;
            
            container.appendChild(star);
        }
    }

    // View Swapping Controller
    function showChatView() {
        state.activeView = "chat";
        elements.chatView.classList.remove("hidden");
        elements.settingsView.classList.add("hidden");
        elements.btnSettings.classList.remove("active");
        elements.chatInput.focus();
    }

    function showSettingsView() {
        state.activeView = "settings";
        elements.settingsView.classList.remove("hidden");
        elements.chatView.classList.add("hidden");
        elements.btnSettings.classList.add("active");
        
        // De-select active chat items in history
        document.querySelectorAll(".history-item").forEach(item => item.classList.remove("active"));
        
        // Refresh speech configuration details in the DOM
        syncSettingsToDOM();
        
        // Fetch debug lists if debug mode is active
        fetchDebugDashboardData();
    }

    // Input height adjustments
    function autoGrowInput() {
        elements.chatInput.style.height = "auto";
        elements.chatInput.style.height = (elements.chatInput.scrollHeight - 16) + "px";
    }

    // Append a message to the chat display
    function appendMessage(sender, text, save = true) {
        // Ensure chat viewport is active
        if (state.activeView !== "chat") {
            showChatView();
        }

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
                
                // Trigger speech reply
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
        
        // Configure voice volume (0.0 to 1.0) and speak speed rate
        utterance.volume = state.settings.voiceVolume / 100;
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

    // Speech Synthesis voice compilation and categorization
    function setupVoiceSynthesis() {
        if (!('speechSynthesis' in window)) return;

        const compileAndPrioritizeVoices = () => {
            // Retrieve all English-related voice modules
            const rawVoices = window.speechSynthesis.getVoices()
                .filter(v => v.lang.startsWith("en") || v.lang.startsWith("en-"));

            // Prioritize higher-quality Online / Natural female voices
            state.voices = rawVoices.sort((a, b) => {
                const getScore = (voice) => {
                    const name = voice.name.toLowerCase();
                    
                    const isOnline = name.includes("online") || name.includes("natural");
                    const isFemale = name.includes("zira") || name.includes("samantha") || 
                                     name.includes("aria") || name.includes("susan") || 
                                     name.includes("hazel") || name.includes("google") || 
                                     name.includes("female");
                    
                    if (isOnline && isFemale) return 4;
                    if (isOnline) return 3;
                    if (isFemale) return 2;
                    return 1;
                };
                
                return getScore(b) - getScore(a);
            });

            // Populate voice picker dropdown
            populateVoiceDropdown();
        };

        compileAndPrioritizeVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = compileAndPrioritizeVoices;
        }
    }

    function populateVoiceDropdown() {
        if (!elements.settingsVoice) return;
        
        elements.settingsVoice.innerHTML = '<option value="">(Default System Voice)</option>';
        
        state.voices.forEach(v => {
            const name = v.name.toLowerCase();
            const isOnline = name.includes("online") || name.includes("natural");
            const isFemale = name.includes("zira") || name.includes("samantha") || 
                             name.includes("aria") || name.includes("susan") || 
                             name.includes("hazel") || name.includes("google") || 
                             name.includes("female");
            
            const genderLabel = isFemale ? "Female" : "Male/General";
            const qualityLabel = isOnline ? "Natural Online" : "Local";
            const isSelected = v.name === state.settings.voiceName ? "selected" : "";
            
            elements.settingsVoice.innerHTML += `
                <option value="${v.name}" ${isSelected}>
                    ${v.name} [${genderLabel} · ${qualityLabel}]
                </option>
            `;
        });
    }

    // Set up DOM event listeners for settings view controls
    function setupSettingsPageBindings() {
        // Voice Reply Toggle Yes/No
        elements.btnSpeechYes.addEventListener("click", () => {
            setSpeechEnabled(true);
        });
        elements.btnSpeechNo.addEventListener("click", () => {
            setSpeechEnabled(false);
        });

        // Speech volume slider
        elements.settingsVoiceVolume.addEventListener("input", (e) => {
            const val = parseInt(e.target.value);
            state.settings.voiceVolume = val;
            elements.volumeVal.textContent = val + "%";
            
            // Dynamic speaker icon classes
            if (val === 0) {
                elements.volumeIcon.className = "fa-solid fa-volume-xmark";
            } else if (val < 40) {
                elements.volumeIcon.className = "fa-solid fa-volume-low";
            } else {
                elements.volumeIcon.className = "fa-solid fa-volume-high";
            }
            saveSettings();
        });

        // Voice Tone Dropdown Select
        elements.settingsVoice.addEventListener("change", (e) => {
            state.settings.voiceName = e.target.value;
            saveSettings();
            speakText("Selected voice tone.");
        });

        // Speed Slider
        elements.settingsVoiceRate.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            state.settings.voiceRate = val;
            elements.rateVal.textContent = val.toFixed(1) + "x";
            saveSettings();
        });

        // Avatar Mode selector
        elements.settingsAvatarMode.addEventListener("change", (e) => {
            state.settings.movementMode = e.target.value;
            saveSettings();
            if (state.settings.movementMode === "drag") {
                // Returns avatar smoothly to bottom right corner coordinates
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
    }

    function setSpeechEnabled(enabled) {
        state.settings.speechEnabled = enabled;
        saveSettings();
        
        if (enabled) {
            elements.btnSpeechYes.classList.add("active");
            elements.btnSpeechNo.classList.remove("active");
            elements.volumeSettingsGroup.classList.remove("hidden");
            speakText("Voice response active.");
        } else {
            elements.btnSpeechNo.classList.add("active");
            elements.btnSpeechYes.classList.remove("active");
            elements.volumeSettingsGroup.classList.add("hidden");
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
        }
    }

    // Synchronize loaded state parameters to DOM elements on settings view enter
    function syncSettingsToDOM() {
        if (state.settings.speechEnabled) {
            elements.btnSpeechYes.classList.add("active");
            elements.btnSpeechNo.classList.remove("active");
            elements.volumeSettingsGroup.classList.remove("hidden");
        } else {
            elements.btnSpeechNo.classList.add("active");
            elements.btnSpeechYes.classList.remove("active");
            elements.volumeSettingsGroup.classList.add("hidden");
        }

        elements.settingsVoiceVolume.value = state.settings.voiceVolume;
        elements.volumeVal.textContent = state.settings.voiceVolume + "%";
        
        elements.settingsVoiceRate.value = state.settings.voiceRate;
        elements.rateVal.textContent = state.settings.voiceRate.toFixed(1) + "x";
        
        elements.settingsAvatarMode.value = state.settings.movementMode;
        
        populateVoiceDropdown();
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
                } else {
                    elements.btnDebug.classList.remove("active");
                    elements.debugStateText.textContent = "OFF";
                }
                
                // Toggle dashboard data when active view is settings and state transitions
                if (state.debug !== data.debug) {
                    state.debug = data.debug;
                    if (state.activeView === "settings") {
                        fetchDebugDashboardData();
                    }
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

    // Fetch errors & suggestions dynamically to render on the settings page
    async function fetchDebugDashboardData() {
        if (!state.debug) {
            elements.suggestionsList.innerHTML = '<p class="pane-placeholder">Debug mode is off. Enable debug mode in the sidebar footer to view suggestions.</p>';
            elements.errorsList.innerHTML = '<p class="pane-placeholder">Debug mode is off. Enable debug mode in the sidebar footer to view error logs.</p>';
            return;
        }

        elements.suggestionsList.innerHTML = '<div class="loading-shimmer" style="height: 60px;"></div>';
        elements.errorsList.innerHTML = '<div class="loading-shimmer" style="height: 60px;"></div>';

        // Retrieve suggestions
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
                    html = `<p class="pane-placeholder">${items[0]}</p>`;
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
                elements.suggestionsList.innerHTML = html;
            }
        } catch (error) {
            elements.suggestionsList.innerHTML = '<p class="pane-placeholder" style="color:#ff0844;">Failed to retrieve system suggestions.</p>';
        }

        // Retrieve errors
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
                    html = `<p class="pane-placeholder">${items[0]}</p>`;
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
                                <div style="margin-top: 4px; font-family: monospace; font-size:0.75rem; word-break: break-all;">${msg.trim()}</div>
                            </div>
                        `;
                    });
                }
                elements.errorsList.innerHTML = html;
            }
        } catch (error) {
            elements.errorsList.innerHTML = '<p class="pane-placeholder" style="color:#ff0844;">Failed to retrieve error logs.</p>';
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
                } else {
                    elements.btnDebug.classList.remove("active");
                    elements.debugStateText.textContent = "OFF";
                }
                
                // Refresh dashboard listings
                if (state.activeView === "settings") {
                    fetchDebugDashboardData();
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
            // Cancel active audio
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

            if (e.type === "touchmove") {
                e.preventDefault();
            }

            const clientX = e.type === "touchmove" ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === "touchmove" ? e.touches[0].clientY : e.clientY;

            let x = clientX - startX;
            let y = clientY - startY;

            // Viewport clamping
            const rect = orb.getBoundingClientRect();
            const maxX = window.innerWidth - rect.width;
            const maxY = window.innerHeight - rect.height;

            x = Math.max(0, Math.min(x, maxX));
            y = Math.max(0, Math.min(y, maxY));

            displacementX = x - state.wanderX;
            displacementY = y - state.wanderY;

            state.wanderX = x;
            state.wanderY = y;

            orb.style.left = x + "px";
            orb.style.top = y + "px";
            orb.style.right = "auto";
            orb.style.bottom = "auto";
        }

        function dragEnd(e) {
            if (!state.isDragging) return;
            state.isDragging = false;

            orb.style.transition = "box-shadow 0.5s ease";
            orb.style.animationPlayState = "running";

            state.targetX = null;
            state.targetY = null;

            const distanceMoved = Math.sqrt(displacementX * displacementX + displacementY * displacementY);

            // Tap gesture threshold
            if (distanceMoved < 6) {
                playOrbGreeting();
            }
        }
    }

    function initWanderCoordinates() {
        const orb = elements.lyraAvatar;
        const rect = orb.getBoundingClientRect();
        
        state.wanderX = rect.left;
        state.wanderY = rect.top;
        
        orb.style.left = state.wanderX + "px";
        orb.style.top = state.wanderY + "px";
        orb.style.right = "auto";
        orb.style.bottom = "auto";
    }

    // Autonomous wandering animation loop
    function avatarWanderLoop() {
        const orb = elements.lyraAvatar;
        const mode = state.settings.movementMode;
        const shouldWander = (mode === "wander" || mode === "both");

        if (shouldWander && !state.isDragging) {
            const rect = orb.getBoundingClientRect();

            if (state.targetX === null || state.targetY === null) {
                const margin = 40;
                const maxX = window.innerWidth - rect.width - margin;
                const maxY = window.innerHeight - rect.height - margin;
                
                state.targetX = Math.random() * (maxX - margin) + margin;
                state.targetY = Math.random() * (maxY - margin) + margin;
            }

            const dx = state.targetX - state.wanderX;
            const dy = state.targetY - state.wanderY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 10) {
                state.targetX = null;
                state.targetY = null;
            } else {
                const step = Math.min(dist, state.wanderSpeed);
                state.wanderX += (dx / dist) * step;
                state.wanderY += (dy / dist) * step;

                orb.style.left = state.wanderX + "px";
                orb.style.top = state.wanderY + "px";
                orb.style.right = "auto";
                orb.style.bottom = "auto";
            }
        } else if (!shouldWander && !state.isDragging && (orb.style.left === "" || orb.style.left === "0px")) {
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
        
        document.querySelectorAll(".history-item").forEach(item => {
            item.classList.remove("active");
            if (item.getAttribute("data-id") === id) {
                item.classList.add("active");
            }
        });

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
        
        showChatView();
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

    // ==========================================
    // Command Palette (Ctrl+K)
    // ==========================================
    function setupCommandPalette() {
        const overlay = document.getElementById("cmd-palette");
        const searchInput = document.getElementById("cmd-search");
        const resultsContainer = document.getElementById("cmd-results");
        let selectedIndex = 0;

        // Available commands registry
        const commands = [
            { label: "New Chat", icon: "fa-plus", action: () => { startNewChat(); showChatView(); } },
            { label: "Open Settings", icon: "fa-gear", action: showSettingsView },
            { label: "Toggle Debug Mode", icon: "fa-terminal", action: toggleDebugMode },
            { label: "Toggle Voice On/Off", icon: "fa-volume-high", action: () => setSpeechEnabled(!state.settings.speechEnabled) },
            { label: "Clear Chat History", icon: "fa-trash", action: () => { localStorage.removeItem("lyra_chat_sessions"); state.sessions = {}; updateHistorySidebar(); startNewChat(); showChatView(); } },
            { label: "Go to Home Page", icon: "fa-house", action: () => { window.location.href = "/"; } },
        ];

        function openPalette() {
            overlay.classList.remove("hidden");
            searchInput.value = "";
            selectedIndex = 0;
            renderResults(commands);
            setTimeout(() => searchInput.focus(), 50);
        }

        function closePalette() {
            overlay.classList.add("hidden");
            searchInput.value = "";
        }

        function renderResults(filteredCmds) {
            resultsContainer.innerHTML = "";
            filteredCmds.forEach((cmd, i) => {
                const item = document.createElement("div");
                item.className = `cmd-item ${i === selectedIndex ? "selected" : ""}`;
                item.innerHTML = `<i class="fa-solid ${cmd.icon}"></i><span class="cmd-item-label">${cmd.label}</span>`;
                item.addEventListener("click", () => {
                    cmd.action();
                    closePalette();
                });
                resultsContainer.appendChild(item);
            });
        }

        function getFilteredCommands() {
            const query = searchInput.value.toLowerCase().trim();
            if (!query) return commands;
            return commands.filter(c => c.label.toLowerCase().includes(query));
        }

        // Keyboard: Ctrl+K to open
        document.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                if (overlay.classList.contains("hidden")) {
                    openPalette();
                } else {
                    closePalette();
                }
            }

            if (!overlay.classList.contains("hidden")) {
                if (e.key === "Escape") {
                    closePalette();
                } else if (e.key === "ArrowDown") {
                    e.preventDefault();
                    const filtered = getFilteredCommands();
                    selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
                    renderResults(filtered);
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    selectedIndex = Math.max(selectedIndex - 1, 0);
                    renderResults(getFilteredCommands());
                } else if (e.key === "Enter") {
                    e.preventDefault();
                    const filtered = getFilteredCommands();
                    if (filtered[selectedIndex]) {
                        filtered[selectedIndex].action();
                        closePalette();
                    }
                }
            }
        });

        // Search filtering
        searchInput.addEventListener("input", () => {
            selectedIndex = 0;
            renderResults(getFilteredCommands());
        });

        // Click outside to close
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) closePalette();
        });
    }
});
