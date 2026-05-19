document.addEventListener('DOMContentLoaded', () => {
    const PLANNER_URL = window.STREAMLIT_URL || 'https://ayuseva-planner.streamlit.app/';
    const sendButton = document.getElementById('send-button');
    const voiceButton = document.getElementById('voice-button');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const loadingIndicator = document.getElementById('loading-indicator');
    const plannerButton = document.getElementById('planner-button');
    const srAnnouncer = document.querySelector('[role="status"]');

    // Speech state
    let currentSpeech = null;
    let isPaused = false;

    // ═══════════════════════════════════════════════════════════════════════
    //   SPEECH RECOGNITION
    // ═══════════════════════════════════════════════════════════════════════
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.interimResults = true;
        recognition.maxAlternatives = 3;

        voiceButton.style.display = 'flex';
        voiceButton.disabled = false;

        voiceButton.addEventListener('click', () => {
            try {
                recognition.start();
                voiceButton.classList.add('listening');
                voiceButton.setAttribute('aria-label', 'Listening...');
                if (srAnnouncer) srAnnouncer.textContent = 'Voice input started. Speak now.';
            } catch (error) {
                console.error('Speech recognition start error:', error);
                if (srAnnouncer) srAnnouncer.textContent = 'Error starting voice input. Please try again.';
                voiceButton.classList.remove('listening');
            }
        });

        recognition.onresult = (event) => {
            let finalTranscript = '';
            for (let i = 0; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                }
            }
            if (finalTranscript) {
                userInput.value = finalTranscript;
                voiceButton.classList.remove('listening');
                voiceButton.setAttribute('aria-label', 'Voice input');
                if (srAnnouncer) srAnnouncer.textContent = `Voice input received: ${finalTranscript}`;
                sendMessage();
            }
        };

        recognition.onend = () => {
            voiceButton.classList.remove('listening');
            voiceButton.setAttribute('aria-label', 'Voice input');
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            voiceButton.classList.remove('listening');
            if (srAnnouncer) {
                const msgs = {
                    'no-speech': 'No speech detected. Please try again.',
                    'not-allowed': 'Microphone access denied. Please allow microphone permissions.',
                };
                srAnnouncer.textContent = msgs[event.error] || `Speech recognition error: ${event.error}`;
            }
        };
    } else {
        voiceButton.disabled = true;
        voiceButton.setAttribute('aria-label', 'Voice input not supported');
        voiceButton.style.opacity = '0.4';
        voiceButton.style.cursor = 'not-allowed';
    }

    // ═══════════════════════════════════════════════════════════════════════
    //   INITIALIZE
    // ═══════════════════════════════════════════════════════════════════════

    initializeChat();

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
    });

    if (plannerButton) {
        plannerButton.href = PLANNER_URL;
        plannerButton.addEventListener('click', (event) => {
            event.preventDefault();

            const plannerWindow = window.open(PLANNER_URL, '_blank', 'noopener,noreferrer');
            if (!plannerWindow) {
                window.location.href = PLANNER_URL;
            }

            if (srAnnouncer) srAnnouncer.textContent = 'Opening Health & Fitness Planner in a new tab.';
        });
    }

    // Responsive resize
    window.addEventListener('resize', () => {
        const container = document.querySelector('.chat-container');
        if (container && window.innerWidth > 768) {
            container.style.height = `${window.innerHeight * 0.88}px`;
        }
    });
    window.dispatchEvent(new Event('resize'));

    // ═══════════════════════════════════════════════════════════════════════
    //   CORE FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function initializeChat() {
        // Light mode only — ensure class is set
        document.body.classList.add('light-mode');

        // Welcome messages
        appendMessage(createMedicalDisclaimer(), 'bot');
        appendMessage(createWelcomeMessage('Welcome to AyuSeva! 🩺', 'I\'m your AI Medical Assistant. Describe your symptoms or ask any health-related question to get started.'), 'bot');

        // First-time tutorial
        if (localStorage.getItem('tutorialShown') !== 'true') {
            showTutorial();
        }
    }

    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        appendMessage(message, 'user');
        userInput.value = '';
        scrollToBottom();
        showLoading(true);

        if (isFirstSymptomInput()) {
            fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symptoms: message }),
            })
            .then(r => r.json())
            .then(data => {
                if (data.maintenance) {
                    appendMessage(createDisclaimer('🔧 Maintenance:', data.message), 'bot');
                } else if (data.error) {
                    appendMessage(createDisclaimer('🔧 Maintenance:', 'AyuSeva is currently under maintenance. Please try again later.'), 'bot');
                } else {
                    if (data.quota_exceeded) {
                        displayFormattedResponse(data, true);
                        appendMessage(createDisclaimer('ℹ️ Note:', 'AyuSeva is currently under maintenance. Detailed medical information is temporarily unavailable.'), 'bot');
                    } else {
                        displayFormattedResponse(data, false);
                    }
                }
                scrollToBottom();
            })
            .catch(err => {
                console.error('Predict error:', err);
                appendMessage('An error occurred while processing your request.', 'bot');
            })
            .finally(() => showLoading(false));
        } else {
            if (['exit', 'quit', 'bye', 'goodbye', 'thank you', 'thanks', 'thankyou'].includes(message.toLowerCase())) {
                appendMessage('Goodbye! Take care and stay healthy 🙏', 'bot');
                showLoading(false);
                // Reset chat after a short delay so user sees the goodbye
                setTimeout(() => {
                    chatMessages.replaceChildren();
                    appendMessage(createMedicalDisclaimer(), 'bot');
                    appendMessage(createWelcomeMessage('Welcome back to AyuSeva! 🩺', 'Describe your symptoms to get a new health assessment.'), 'bot');
                    scrollToBottom();
                }, 2500);
                return;
            }

            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            })
            .then(r => r.json())
            .then(data => {
                data.error
                    ? appendMessage(`Error: ${data.error}`, 'bot')
                    : appendMessage(data.message, 'bot');
                scrollToBottom();
                
                if (data.reset) {
                    setTimeout(() => window.location.reload(), 2500);
                }
            })
            .catch(err => {
                console.error('Chat error:', err);
                appendMessage('An error occurred while processing your request.', 'bot');
            })
            .finally(() => showLoading(false));
        }
    }

    function appendMessage(content, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender);
        msgDiv.setAttribute('role', 'log');
        msgDiv.setAttribute('aria-live', 'polite');

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');

        if (content instanceof Node) {
            contentDiv.appendChild(content);
        } else {
            appendTextWithLineBreaks(contentDiv, String(content));
        }

        msgDiv.appendChild(contentDiv);

        if (sender === 'bot') {
            const actionsDiv = document.createElement('div');
            actionsDiv.classList.add('message-actions');

            const speechBtn = document.createElement('button');
            speechBtn.classList.add('speech-button');
            speechBtn.setAttribute('aria-label', 'Play speech');
            speechBtn.appendChild(createSpeechIcon('🔊'));
            speechBtn.dataset.state = 'play';
            speechBtn.onclick = () => toggleSpeech(contentDiv.textContent.trim(), speechBtn);

            actionsDiv.appendChild(speechBtn);
            msgDiv.appendChild(actionsDiv);
        }

        requestAnimationFrame(() => {
            chatMessages.appendChild(msgDiv);
            scrollToBottom();
        });

        if (srAnnouncer) {
            srAnnouncer.textContent = `${sender === 'user' ? 'You' : 'AyuSeva'}: ${contentDiv.textContent}`;
        }
    }

    function appendTextWithLineBreaks(container, text) {
        text.split('\n').forEach((line, index) => {
            if (index > 0) container.appendChild(document.createElement('br'));
            appendFormattedLine(container, line);
        });
    }

    function appendFormattedLine(container, line) {
        // Strip leading '* ' or '- ' (markdown list markers)
        line = line.replace(/^\s*[\*\-]\s+/, '');
        // Strip any stray asterisks (from **bold** markdown)
        line = line.replace(/\*\*/g, '').replace(/\*/g, '');
        // Auto-bold text before the first colon (e.g. "Abscess rupture: description")
        const colonIdx = line.indexOf(':');
        if (colonIdx > 0 && colonIdx < 60) {
            const strong = document.createElement('strong');
            strong.textContent = line.slice(0, colonIdx + 1);
            container.appendChild(strong);
            container.appendChild(document.createTextNode(line.slice(colonIdx + 1)));
        } else {
            container.appendChild(document.createTextNode(line));
        }
    }

    function createSpeechIcon(symbol) {
        const icon = document.createElement('span');
        icon.classList.add('speech-icon');
        icon.textContent = symbol;
        return icon;
    }

    function setSpeechIcon(button, symbol) {
        button.replaceChildren(createSpeechIcon(symbol));
    }

    function createDisclaimer(title, message) {
        const wrapper = document.createElement('div');
        wrapper.classList.add('disclaimer');

        const strong = document.createElement('strong');
        strong.textContent = title;
        wrapper.appendChild(strong);

        const paragraph = document.createElement('p');
        paragraph.textContent = message;
        wrapper.appendChild(paragraph);

        return wrapper;
    }

    function createMedicalDisclaimer() {
        return createDisclaimer(
            '⚠️ Medical Disclaimer',
            'This assistant provides preliminary symptom analysis only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider.'
        );
    }

    function createWelcomeMessage(titleText, bodyText) {
        const wrapper = document.createElement('div');

        const title = document.createElement('strong');
        title.textContent = titleText;
        wrapper.appendChild(title);
        wrapper.appendChild(document.createElement('br'));
        wrapper.appendChild(document.createTextNode(bodyText));

        return wrapper;
    }

    function createSection(title, items) {
        const wrapper = document.createElement('div');
        wrapper.classList.add('section');

        const heading = document.createElement('strong');
        heading.classList.add('section-title');
        heading.textContent = title;
        wrapper.appendChild(heading);

        const list = document.createElement('ul');
        items.forEach(item => {
            const listItem = document.createElement('li');
            appendFormattedLine(listItem, String(item));
            list.appendChild(listItem);
        });
        wrapper.appendChild(list);

        return wrapper;
    }

    function isFirstSymptomInput() {
        return chatMessages.querySelectorAll('.bot').length === 2;
    }

    // ═══════════════════════════════════════════════════════════════════════
    //   FORMATTED PREDICTION RESPONSE
    // ═══════════════════════════════════════════════════════════════════════

    function displayFormattedResponse(data, isMaintenance = false) {
        const section = createSection;

        if (data.predicted_disease) {
            // Only show prediction if we are NOT in maintenance, OR if we are and confidence > 95%
            if (!isMaintenance || (isMaintenance && data.confidence > 95)) {
                appendMessage(section('🩺 Predicted Disease', [data.predicted_disease]), 'bot');
            } else if (isMaintenance && data.confidence <= 95) {
                appendMessage(section('🩺 Status', ['Diagnosis requires deeper AI analysis which is currently down.']), 'bot');
            }
        }
        if (data.symptoms?.length)
            appendMessage(section('🤒 Symptoms Analyzed', data.symptoms), 'bot');
        if (data.additional_symptoms?.length)
            appendMessage(section('🩹 Additional Symptoms', data.additional_symptoms), 'bot');
        if (data.precautions?.length)
            appendMessage(section('🛡️ Precautions', data.precautions), 'bot');
        if (data.preventive_measures?.length)
            appendMessage(section('🔒 Preventive Measures', data.preventive_measures), 'bot');
        if (data.medications?.length)
            appendMessage(section('💊 Medications', data.medications), 'bot');
        if (data.treatments?.length)
            appendMessage(section('⚕️ Treatments', data.treatments), 'bot');
        if (data.diet?.length)
            appendMessage(section('🥗 Diet Recommendations', data.diet), 'bot');
        if (data.medical_advice?.length)
            appendMessage(section('📋 Medical Advice', data.medical_advice), 'bot');
        if (data.complications?.length)
            appendMessage(section('⚠️ Complications', data.complications), 'bot');
    }

    // ═══════════════════════════════════════════════════════════════════════
    //   SPEECH SYNTHESIS
    // ═══════════════════════════════════════════════════════════════════════

    function toggleSpeech(text, button) {
        const state = button.dataset.state;

        if (state === 'play') {
            stopAllSpeech();
            const cleaned = text.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '').trim();
            currentSpeech = new SpeechSynthesisUtterance(cleaned);
            currentSpeech.lang = 'en-GB';
            currentSpeech.volume = 1;
            currentSpeech.rate = 1.05;
            currentSpeech.pitch = 1;

            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(currentSpeech);

            button.dataset.state = 'pause';
            setSpeechIcon(button, '⏸️');
            button.setAttribute('aria-label', 'Pause speech');

            currentSpeech.onend = () => {
                button.dataset.state = 'play';
                setSpeechIcon(button, '🔊');
                button.setAttribute('aria-label', 'Play speech');
                isPaused = false;
            };
        } else if (state === 'pause') {
            window.speechSynthesis.pause();
            isPaused = true;
            button.dataset.state = 'resume';
            setSpeechIcon(button, '▶️');
            button.setAttribute('aria-label', 'Resume speech');
        } else if (state === 'resume') {
            window.speechSynthesis.resume();
            isPaused = false;
            button.dataset.state = 'pause';
            setSpeechIcon(button, '⏸️');
            button.setAttribute('aria-label', 'Pause speech');
        }
    }

    function stopAllSpeech() {
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
            window.speechSynthesis.cancel();
            isPaused = false;
            currentSpeech = null;
            document.querySelectorAll('.speech-button').forEach(btn => {
                btn.dataset.state = 'play';
                setSpeechIcon(btn, '🔊');
                btn.setAttribute('aria-label', 'Play speech');
            });
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //   UTILITIES
    // ═══════════════════════════════════════════════════════════════════════

    function scrollToBottom() {
        requestAnimationFrame(() => {
            const chatWindow = document.getElementById('chat-window');
            chatWindow.scrollTop = chatWindow.scrollHeight;
        });
    }

    function showLoading(show) {
        loadingIndicator.style.display = show ? 'flex' : 'none';
        if (show && srAnnouncer) srAnnouncer.textContent = 'AyuSeva is analyzing...';
    }

    function showTutorial() {
        const modal = document.createElement('div');
        modal.classList.add('modal');

        const modalContent = document.createElement('div');
        modalContent.classList.add('modal-content');

        const icon = document.createElement('span');
        icon.classList.add('modal-icon');
        icon.textContent = '🩺';
        modalContent.appendChild(icon);

        const title = document.createElement('h2');
        title.textContent = 'Welcome to AyuSeva';
        modalContent.appendChild(title);

        ['Type your symptoms to get an AI-powered health assessment.', 'Use the 🎙️ mic for voice input.'].forEach(text => {
            const paragraph = document.createElement('p');
            paragraph.textContent = text;
            modalContent.appendChild(paragraph);
        });

        const plannerText = document.createElement('p');
        plannerText.appendChild(document.createTextNode('Access the '));
        const plannerLabel = document.createElement('strong');
        plannerLabel.textContent = 'Health & Fitness Planner';
        plannerText.appendChild(plannerLabel);
        plannerText.appendChild(document.createTextNode(' anytime from the header button.'));
        modalContent.appendChild(plannerText);

        const closeButton = document.createElement('button');
        closeButton.classList.add('modal-close');
        closeButton.textContent = 'Get Started';
        modalContent.appendChild(closeButton);

        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        closeButton.addEventListener('click', () => {
            modal.remove();
            localStorage.setItem('tutorialShown', 'true');
        });

        if (srAnnouncer) srAnnouncer.textContent = 'Welcome tutorial opened.';
    }
});
