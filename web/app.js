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
        sessions: {} // { id: { title: "", messages: [...] } }
    };

    // DOM Elements
    const elements = {
        messagesArea: document.getElementById("chat-messages"),
        chatInput: document.getElementById("chat-input"),
        btnSend: document.getElementById("btn-send"),
        btnMic: document.getElementById("btn-mic"),
        lyraAvatar: document.getElementById("lyra-avatar"),
        avatarTooltip: document.getElementById("avatar-tooltip"),
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
        welcomeView: document.getElementById("welcome-view")
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

        // Set up draggable floating avatar
        setupDraggableAvatar();

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
                
                // Trigger web speech synthesis for spoken outputs
                if (data.speak && 'speechSynthesis' in window) {
                    const utterance = new SpeechSynthesisUtterance(data.response);
                    utterance.rate = 1.05;
                    window.speechSynthesis.speak(utterance);
                }
            } else {
                appendMessage("agent", `Error: ${data.error || "failed to communicate with Lyra core."}`);
            }
        } catch (error) {
            appendMessage("agent", "Could not reach Lyra web server. Make sure the server script is running.");
            console.error("Chat error:", error);
        }
    }

    // Set Avatar Mood Classes & Tooltip
    function setOrbMood(mood) {
        const validMoods = ["casual", "focused", "concerned", "alert", "curious", "playful"];
        if (!validMoods.includes(mood)) mood = "casual";

        // Remove other classes
        validMoods.forEach(m => elements.lyraAvatar.classList.remove(m));
        
        // Add new class
        elements.lyraAvatar.classList.add(mood);
        state.mood = mood;

        // Update tooltip text
        elements.avatarTooltip.textContent = mood.charAt(0).toUpperCase() + mood.slice(1) + " Mood";
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
        
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(greet);
            utterance.rate = 1.05;
            window.speechSynthesis.speak(utterance);
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

    // Modal helpers
    function showModal(title, htmlContent) {
        elements.modalTitle.textContent = title;
        elements.modalBody.innerHTML = htmlContent;
        elements.modalOverlay.classList.remove("hidden");
        // Force reflow for fade animation
        elements.modalOverlay.offsetHeight;
        elements.modalOverlay.classList.add("visible");
    }

    function hideModal() {
        elements.modalOverlay.classList.remove("visible");
        setTimeout(() => {
            elements.modalOverlay.classList.add("hidden");
        }, 300);
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
    // Floating Draggable Avatar Orb Code
    // ==========================================
    function setupDraggableAvatar() {
        const orb = elements.lyraAvatar;
        let isDragging = false;
        let startX, startY;
        let initialX, initialY;
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
            isDragging = true;
            orb.style.transition = "none";
            orb.style.animationPlayState = "paused";

            const clientX = e.type === "touchstart" ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === "touchstart" ? e.touches[0].clientY : e.clientY;

            // Get absolute current top/left coordinates
            const rect = orb.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;

            startX = clientX - initialX;
            startY = clientY - initialY;
            
            displacementX = 0;
            displacementY = 0;
        }

        function dragMove(e) {
            if (!isDragging) return;

            // Prevent scroll on mobile touch events
            if (e.type === "touchmove") {
                e.preventDefault();
            }

            const clientX = e.type === "touchmove" ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === "touchmove" ? e.touches[0].clientY : e.clientY;

            // Calculate new position
            let x = clientX - startX;
            let y = clientY - startY;

            // Keep within viewport boundaries
            const rect = orb.getBoundingClientRect();
            const maxX = window.innerWidth - rect.width;
            const maxY = window.innerHeight - rect.height;

            x = Math.max(0, Math.min(x, maxX));
            y = Math.max(0, Math.min(y, maxY));

            // Track displacement to check for a tap/click action vs a drag movement
            displacementX = x - initialX;
            displacementY = y - initialY;

            // Apply style coordinates
            orb.style.left = x + "px";
            orb.style.top = y + "px";
            orb.style.right = "auto";
            orb.style.bottom = "auto";
        }

        function dragEnd(e) {
            if (!isDragging) return;
            isDragging = false;

            // Restore smooth visual float animation
            orb.style.transition = "box-shadow 0.5s ease";
            orb.style.animationPlayState = "running";

            const distanceMoved = Math.sqrt(displacementX * displacementX + displacementY * displacementY);

            // Click threshold: If user moved orb less than 5px, count it as a click/tap
            if (distanceMoved < 6) {
                playOrbGreeting();
            }
        }
    }

    // ==========================================
    // Session History Sidebar Management
    // ==========================================
    function startNewChat() {
        if (state.activeSession && state.sessions[state.activeSession].messages.length === 0) {
            // Already in a blank session
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
        
        // Sort sessions by date (descending)
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
