/* ==========================================
   Lyra Web Interface - Frontend Client Logic
   ========================================== */

document.addEventListener("DOMContentLoaded", () => {
    // State management
    const state = {
        mood: "casual",
        debug: false,
        isRecording: false,
        recognition: null
    };

    // DOM Elements
    const elements = {
        messagesArea: document.getElementById("chat-messages"),
        chatInput: document.getElementById("chat-input"),
        btnSend: document.getElementById("btn-send"),
        btnMic: document.getElementById("btn-mic"),
        lyraAvatar: document.getElementById("lyra-avatar"),
        lyraMoodTitle: document.getElementById("lyra-mood-title"),
        lyraTimeTitle: document.getElementById("lyra-time-title"),
        memoryCategories: document.getElementById("memory-categories"),
        statusSpotify: document.getElementById("status-spotify"),
        statusGmail: document.getElementById("status-gmail"),
        statusClassroom: document.getElementById("status-classroom"),
        statusWhatsapp: document.getElementById("status-whatsapp"),
        modelIndicator: document.getElementById("model-indicator"),
        debugStateText: document.getElementById("debug-state"),
        btnSuggestions: document.getElementById("btn-suggestions"),
        btnErrors: document.getElementById("btn-errors"),
        btnDebug: document.getElementById("btn-debug"),
        modalOverlay: document.getElementById("modal-container"),
        modalTitle: document.getElementById("modal-title"),
        modalBody: document.getElementById("modal-body"),
        btnCloseModal: document.getElementById("btn-close-modal")
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

        // Sidebar utility action listeners
        elements.btnSuggestions.addEventListener("click", fetchSuggestions);
        elements.btnErrors.addEventListener("click", fetchErrors);
        elements.btnDebug.addEventListener("click", toggleDebugMode);

        // Modal close listeners
        elements.btnCloseModal.addEventListener("click", hideModal);
        elements.modalOverlay.addEventListener("click", (e) => {
            if (e.target === elements.modalOverlay) hideModal();
        });

        // Orb interactive greeting
        elements.lyraAvatar.addEventListener("click", playOrbGreeting);

        // Initial data load
        updateSystemStatus();
        updateMemoryCategories();

        // Focus input
        elements.chatInput.focus();

        // Refresh status every 15 seconds
        setInterval(updateSystemStatus, 15000);
    }

    // Input height adjustments
    function autoGrowInput() {
        elements.chatInput.style.height = "auto";
        elements.chatInput.style.height = (elements.chatInput.scrollHeight - 16) + "px";
    }

    // Append a message to the chat display
    function appendMessage(sender, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}-msg`;
        
        const p = document.createElement("p");
        p.textContent = text;
        msgDiv.appendChild(p);
        
        elements.messagesArea.appendChild(msgDiv);
        elements.messagesArea.scrollTop = elements.messagesArea.scrollHeight;
        
        // Remove typing indicator if present
        removeTypingIndicator();
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
                if (data.time) {
                    elements.lyraTimeTitle.textContent = data.time;
                }
                
                // Trigger web speech synthesis for spoken outputs if appropriate
                if (data.speak && 'speechSynthesis' in window) {
                    const utterance = new SpeechSynthesisUtterance(data.response);
                    // Match speech settings
                    utterance.rate = 1.05;
                    utterance.pitch = 1.0;
                    window.speechSynthesis.speak(utterance);
                }
                
                // Refresh memory/integrations in case it learned something or updated state
                updateMemoryCategories();
                updateSystemStatus();
            } else {
                appendMessage("agent", `Error: ${data.error || "failed to communicate with Lyra core."}`);
            }
        } catch (error) {
            appendMessage("agent", "Could not reach Lyra web server. Make sure the server script is running.");
            console.error("Chat error:", error);
        }
    }

    // Set Avatar Mood Classes & Label
    function setOrbMood(mood) {
        const validMoods = ["casual", "focused", "concerned", "alert", "curious", "playful"];
        if (!validMoods.includes(mood)) mood = "casual";

        // Remove other classes
        validMoods.forEach(m => elements.lyraAvatar.classList.remove(m));
        
        // Add new class
        elements.lyraAvatar.classList.add(mood);
        state.mood = mood;

        // Capitalize title
        elements.lyraMoodTitle.textContent = mood.charAt(0).toUpperCase() + mood.slice(1) + " Mood";
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

    // Fetch and render memory categories
    async function updateMemoryCategories() {
        try {
            const response = await fetch("/api/memory");
            const data = await response.json();
            
            if (data.status === "ok" && data.categories) {
                elements.memoryCategories.innerHTML = "";
                
                if (data.categories.length === 0) {
                    elements.memoryCategories.innerHTML = '<p style="color:var(--text-muted); font-size:0.8rem; width:100%;">No memory profiles yet.</p>';
                    return;
                }
                
                data.categories.forEach(cat => {
                    const tag = document.createElement("div");
                    tag.className = "category-tag";
                    tag.textContent = cat;
                    tag.addEventListener("click", () => {
                        elements.chatInput.value = `Tell me about my memory category: ${cat}`;
                        elements.chatInput.focus();
                        autoGrowInput();
                    });
                    elements.memoryCategories.appendChild(tag);
                });
            }
        } catch (error) {
            console.error("Error loading memory categories:", error);
        }
    }

    // Fetch and update system integrations status
    async function updateSystemStatus() {
        try {
            const response = await fetch("/api/status");
            const data = await response.json();
            
            if (data.status === "ok") {
                // Update integration indicators
                updateIndicator(elements.statusSpotify, data.services.spotify);
                updateIndicator(elements.statusGmail, data.services.gmail);
                updateIndicator(elements.statusClassroom, data.services.classroom);
                updateIndicator(elements.statusWhatsapp, data.services.whatsapp);

                // Update info panels
                elements.modelIndicator.textContent = data.model;
                elements.debugStateText.textContent = data.debug ? "ON" : "OFF";
                state.debug = data.debug;

                if (data.mood) {
                    setOrbMood(data.mood);
                }
                if (data.time) {
                    elements.lyraTimeTitle.textContent = data.time;
                }
            }
        } catch (error) {
            console.error("Error loading status:", error);
        }
    }

    function updateIndicator(element, online) {
        if (online) {
            element.classList.remove("offline");
            element.classList.add("online");
        } else {
            element.classList.remove("online");
            element.classList.add("offline");
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
                elements.debugStateText.textContent = state.debug ? "ON" : "OFF";
                appendMessage("system", `System debug logs toggled ${state.debug ? "ON" : "OFF"}`);
                
                // Force sync info
                updateSystemStatus();
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
});
