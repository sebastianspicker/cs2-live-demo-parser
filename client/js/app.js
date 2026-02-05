import { msgpack_decode } from "./msgpack.js";
import { processEvents, updateAdvisory } from "./events.js";
import { renderRadar, updateTrails, getInterpolatedPlayers } from "./render.js";

class UIController {
    constructor() {
        this.elements = new Map();
        this.statusIndicator = document.getElementById("statusIndicator");
        this.connectionStatus = document.getElementById("connectionStatus");
        this.statusText = document.getElementById("statusText");
        this.headerStatus = document.getElementById("connectionStatusText");
        this.panelIndicator = document.getElementById("connectionIndicator");
        this.modeSelect = document.getElementById("modeSelector");
        this.demoSelect = document.getElementById("demoSelector");
        this.playbackControls = document.getElementById("playbackControls");
        this.playbackButtons = [
            document.getElementById("playbackPlay"),
            document.getElementById("playbackPause"),
            document.getElementById("playbackBack"),
            document.getElementById("playbackForward"),
        ];
        this.playbackSelect = document.getElementById("playbackSpeed");
        this.playbackSeek = document.getElementById("playbackSeek");
    }

    getElement(id) {
        if (!this.elements.has(id)) {
            this.elements.set(id, document.getElementById(id));
        }
        return this.elements.get(id);
    }

    updateConnectionStatus(connected) {
        if (connected) {
            this.statusIndicator.classList.remove("disconnected");
            this.statusIndicator.classList.add("connected");
            if (this.panelIndicator) {
                this.panelIndicator.classList.remove("disconnected");
                this.panelIndicator.classList.add("connected");
            }
            this.connectionStatus.classList.remove("disconnected");
            this.connectionStatus.classList.add("connected");
            this.statusText.textContent = "✅ Connected";
            if (this.headerStatus) this.headerStatus.textContent = "Connected";
        } else {
            this.statusIndicator.classList.remove("connected");
            this.statusIndicator.classList.add("disconnected");
            if (this.panelIndicator) {
                this.panelIndicator.classList.remove("connected");
                this.panelIndicator.classList.add("disconnected");
            }
            this.connectionStatus.classList.remove("connected");
            this.connectionStatus.classList.add("disconnected");
            this.statusText.textContent = "❌ Reconnecting...";
            if (this.headerStatus) this.headerStatus.textContent = "Reconnecting...";
        }
    }

    updateDemoList(demos) {
        if (!this.demoSelect) return;
        const current = this.demoSelect.value;
        this.demoSelect.textContent = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select demo...";
        this.demoSelect.appendChild(placeholder);
        demos.forEach((demo) => {
            const option = document.createElement("option");
            option.value = demo.name;
            option.textContent = demo.name;
            this.demoSelect.appendChild(option);
        });
        if (current) {
            this.demoSelect.value = current;
        }
    }

    updateModeUI(mode) {
        if (this.modeSelect) this.modeSelect.value = mode;
        if (this.demoSelect) this.demoSelect.disabled = mode !== "manual";
    }

    setPlaybackEnabled(enabled) {
        if (this.playbackControls) {
            this.playbackControls.style.opacity = enabled ? "1" : "0.5";
        }
        this.playbackButtons.forEach((btn) => {
            if (btn) btn.disabled = !enabled;
        });
        if (this.playbackSelect) this.playbackSelect.disabled = !enabled;
        if (this.playbackSeek) this.playbackSeek.disabled = !enabled;
    }
}

class CS2BroadcasterClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.currentMap = "Mirage";
        this.mapConfig = null;
        this.gameState = null;
        this.lastState = null;
        this.currentState = null;
        this.canvas = document.getElementById("radarCanvas");
        this.ctx = this.canvas.getContext("2d");
        this.lastUpdateTime = Date.now();
        this.frameCount = 0;
        this.updateHistory = [];
        this.maxHistory = 100;
        this.lastUpdateReceived = Date.now();
        this.smoothIntervalMs = 800;
        this.trails = new Map();
        this.lastPollIntervalMs = 800;
        this.showTrails = true;
        this.enableSmoothing = true;
        this.utilityEvents = [];
        this.playerStates = new Map();
        this.advisory = null;
        this.advisoryExpiresAt = 0;
        this.statusMessage = "";
        this.statusLevel = "info";
        this.statusExpiresAt = 0;
        this.localStatusMessage = "";
        this.localStatusLevel = "info";
        this.localStatusExpiresAt = 0;
        this.lastParseMs = 0;
        this.avgParseMs = 0;
        this.compressionRate = 0;
        this.msgBytes = 0;
        this.demoRemaining = 0;
        this.demoDataRateBps = 0;
        this.demoTime = 0;
        this.demoTotalTime = 0;
        this.isSeeking = false;
        this.liveLagSec = 0;
        this.demoSpeedPct = 0;
        this.lastDemoTimeSample = null;
        this.lastServerTsSample = null;
        this.mode = "live";
        this.demos = [];
        this.selectedDemo = "";
        this.demoValid = false;
        this.demoLoading = false;
        this.mapOverride = "auto";
        this.boundsSafe = true;
        this.mapImages = new Map();
        this.currentMapImage = null;
        this.mapImageAttempts = new Map();
        this.mapRetryTimers = new Map();
        this.ui = new UIController();
        this.msgpackRefreshInterval = 10;
        this.ui.setPlaybackEnabled(this.mode === "manual");

        this.loadClientConfig();
        this.connect();
        this.setupEventListeners();
        this.startRenderLoop();
    }

    connect() {
        const params = new URLSearchParams(window.location.search);
        const wsOverride = params.get("ws");
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.hostname || "localhost";
        const port = 8765;
        const wsUrl = wsOverride || `${protocol}//${host}:${port}`;

        console.log("🔗 Connecting to:", wsUrl);

        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = "arraybuffer";

        this.ws.onopen = () => {
            this.connected = true;
            this.ui.updateConnectionStatus(true);
            console.log("✅ Connected to broadcaster");
        };

        this.ws.onmessage = async (event) => {
            await this.handleMessage(event.data);
        };

        this.ws.onerror = (error) => {
            console.error("❌ WebSocket error:", error);
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.ui.updateConnectionStatus(false);
            console.log("❌ Disconnected from broadcaster");

            setTimeout(() => this.connect(), 3000);
        };
    }

    sendMessage(payload) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        this.ws.send(JSON.stringify(payload));
    }

    async handleMessage(data) {
        try {
            let message;

            if (data instanceof Blob) {
                data = await data.arrayBuffer();
            }
            if (data instanceof ArrayBuffer || data instanceof Uint8Array) {
                try {
                    message = msgpack_decode(data);
                } catch {
                    const text = new TextDecoder().decode(data);
                    message = JSON.parse(text);
                }
            } else {
                message = JSON.parse(data);
            }

            if (message.type === "position_update") {
                this.handlePositionUpdate(message);
            } else if (message.type === "connection") {
                console.log("✅ Connected:", message.message);
                if (message.mode) {
                    this.mode = message.mode;
                    this.ui.updateModeUI(this.mode);
                }
                if (typeof message.map_override === "string") {
                    this.mapOverride = message.map_override || "auto";
                    this.updateMapOverrideUI();
                }
                if (typeof message.demo_valid === "boolean") {
                    this.demoValid = message.demo_valid;
                    this.updateDemoStatusUI();
                }
                if (typeof message.demo_loading === "boolean") {
                    this.demoLoading = message.demo_loading;
                    this.updateDemoStatusUI();
                }
                if (typeof message.bounds_safe === "boolean") {
                    this.boundsSafe = message.bounds_safe;
                }
                if (typeof message.msgpack_refresh_interval === "number") {
                    this.msgpackRefreshInterval = message.msgpack_refresh_interval;
                    this.updateSamplingUI();
                }
                if (Array.isArray(message.demos)) {
                    this.ui.updateDemoList(message.demos);
                }
                this.selectedDemo = message.selected_demo || "";
                const demoSelect = this.ui.getElement("demoSelector");
                if (demoSelect) demoSelect.value = this.selectedDemo;
                this.ui.setPlaybackEnabled(this.mode === "manual" && !!this.selectedDemo);
                const mapSelector = this.ui.getElement("mapSelector");
                if (mapSelector) mapSelector.value = this.mapOverride;
                this.updateMapOverrideUI();
                this.updateDemoStatusUI();
            } else if (message.type === "demo_list") {
                if (Array.isArray(message.demos)) {
                    this.ui.updateDemoList(message.demos);
                }
                if (message.mode) {
                    this.mode = message.mode;
                    this.ui.updateModeUI(this.mode);
                }
                if (typeof message.selected_demo !== "undefined") {
                    this.selectedDemo = message.selected_demo || "";
                    const demoSelect = this.ui.getElement("demoSelector");
                    if (demoSelect) demoSelect.value = this.selectedDemo;
                }
                if (typeof message.bounds_safe === "boolean") {
                    this.boundsSafe = message.bounds_safe;
                }
                this.ui.setPlaybackEnabled(this.mode === "manual" && !!this.selectedDemo);
                this.updateMapOverrideUI();
                this.updateDemoStatusUI();
            } else if (message.type === "state") {
                if (message.mode) {
                    this.mode = message.mode;
                    this.ui.updateModeUI(this.mode);
                }
                if (typeof message.selected_demo !== "undefined") {
                    this.selectedDemo = message.selected_demo || "";
                    const demoSelect = this.ui.getElement("demoSelector");
                    if (demoSelect) demoSelect.value = this.selectedDemo;
                }
                if (typeof message.map_override === "string") {
                    this.mapOverride = message.map_override || "auto";
                    const mapSelector = this.ui.getElement("mapSelector");
                    if (mapSelector) mapSelector.value = this.mapOverride;
                }
                if (typeof message.demo_valid === "boolean") {
                    this.demoValid = message.demo_valid;
                }
                if (typeof message.demo_loading === "boolean") {
                    this.demoLoading = message.demo_loading;
                }
                if (typeof message.bounds_safe === "boolean") {
                    this.boundsSafe = message.bounds_safe;
                }
                this.ui.setPlaybackEnabled(this.mode === "manual" && !!this.selectedDemo);
                this.updateMapOverrideUI();
                this.updateDemoStatusUI();
            } else if (message.type === "status") {
                const text = typeof message.message === "string" ? message.message : "";
                this.statusMessage = text;
                this.statusLevel = message.level || "info";
                const expiresIn = typeof message.expires_in === "number" ? message.expires_in : 0;
                this.statusExpiresAt = expiresIn > 0 ? Date.now() + expiresIn : Number.POSITIVE_INFINITY;
            }
        } catch (error) {
            console.error("Error handling message:", error);
        }
    }

    handlePositionUpdate(message) {
        if (message.map && message.map !== this.currentMap) {
            this.currentMap = message.map;
            this.mapConfig = message.map_config;
            const currentMapEl = this.ui.getElement("currentMap");
            if (currentMapEl) currentMapEl.textContent = message.map;
            if (this.mapOverride === "auto") {
                const mapSelector = this.ui.getElement("mapSelector");
                if (mapSelector) mapSelector.value = message.map;
            }
            this.loadMapImage(message.map);
        }
        if (message.map_config && !message.map_config.world_bounds) {
            if (!this.localStatusMessage || !this.localStatusMessage.includes("bounds")) {
                this.localStatusMessage = "Map bounds missing; projection may be inaccurate";
                this.localStatusLevel = "warning";
                this.localStatusExpiresAt = Number.POSITIVE_INFINITY;
            }
        } else if (this.localStatusMessage && this.localStatusMessage.includes("bounds")) {
            this.localStatusMessage = "";
            this.localStatusExpiresAt = 0;
        }

        this.lastState = this.currentState;
        this.currentState = message.data;
        this.gameState = message.data;
        this.lastParseMs = message._parse_ms || 0;
        this.avgParseMs = message._avg_parse_ms || 0;
        this.compressionRate = message._compression_rate || 0;
        this.msgBytes = message._msg_bytes || 0;
        this.demoRemaining = message._demo_remaining || 0;
        this.demoDataRateBps = message._demo_data_rate_bps || 0;
        this.demoTime = message._demo_time || 0;
        if (typeof message._demo_remaining === "number") {
            this.demoTotalTime = this.demoTime + this.demoRemaining;
        }
        if (typeof message._live_lag_sec === "number") {
            this.liveLagSec = message._live_lag_sec;
        }
        if (typeof message._server_ts === "number") {
            const serverTs = message._server_ts;
            if (this.lastDemoTimeSample !== null && this.lastServerTsSample !== null) {
                const demoDelta = this.demoTime - this.lastDemoTimeSample;
                const wallDelta = serverTs - this.lastServerTsSample;
                if (wallDelta > 0) {
                    const ratio = demoDelta / wallDelta;
                    this.demoSpeedPct = Math.max(0, Math.min(400, ratio * 100));
                }
            }
            this.lastDemoTimeSample = this.demoTime;
            this.lastServerTsSample = serverTs;
        }
        processEvents(this, message.data.events || []);
        this.updateUI();
        this.updateHistory.push({
            timestamp: Date.now(),
            parseMs: message._parse_ms,
        });
        this.lastUpdateReceived = Date.now();
        if (message._poll_interval) {
            this.lastPollIntervalMs = message._poll_interval * 1000;
        }
        if (this.updateHistory.length >= 2) {
            const last = this.updateHistory[this.updateHistory.length - 1];
            const prev = this.updateHistory[this.updateHistory.length - 2];
            const interval = last.timestamp - prev.timestamp;
            if (interval > 0) {
                this.smoothIntervalMs = Math.max(100, Math.min(2000, interval));
            }
        }
        if (this.lastPollIntervalMs) {
            this.smoothIntervalMs = Math.max(100, Math.min(2000, this.lastPollIntervalMs * 1.2));
        }
        updateTrails(this, this.currentState);

        if (this.updateHistory.length > this.maxHistory) {
            this.updateHistory.shift();
        }
    }

    clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }

    renderPlayerEconomy(element, players) {
        this.clearElement(element);
        const sorted = [...players].sort((a, b) => {
            if (a.team === b.team) {
                return (b.money || 0) - (a.money || 0);
            }
            return a.team === "CT" ? -1 : 1;
        });
        sorted.forEach((player) => {
            const row = document.createElement("div");
            row.className = `player-economy-row ${player.team === "CT" ? "ct" : player.team === "T" ? "t" : ""}`;
            const name = document.createElement("span");
            name.textContent = player.name || "Unknown";
            const money = document.createElement("span");
            money.textContent = `$${player.money || 0}`;
            row.appendChild(name);
            row.appendChild(money);
            element.appendChild(row);
        });
    }

    updateUI() {
        if (!this.gameState) return;

        const data = this.gameState;
        const get = (id) => this.ui.getElement(id);

        const ctScoreEl = get("ctScore");
        const tScoreEl = get("tScore");
        if (ctScoreEl) ctScoreEl.textContent = data.ct_score;
        if (tScoreEl) tScoreEl.textContent = data.t_score;

        const roundNumberEl = get("roundNumber");
        const roundTimeEl = get("roundTime");
        const bombStatusEl = get("bombStatus");
        if (roundNumberEl) roundNumberEl.textContent = data.round;
        if (roundTimeEl) {
            roundTimeEl.textContent = `${Math.floor(data.time / 60)}:${String(Math.floor(data.time % 60)).padStart(2, "0")}`;
        }
        if (bombStatusEl) bombStatusEl.textContent = data.bomb_planted ? "💣 PLANTED" : "Safe";

        const ctBankEl = get("ctBank");
        const tBankEl = get("tBank");
        const ctStatusEl = get("ctStatus");
        const tStatusEl = get("tStatus");
        if (ctBankEl) ctBankEl.textContent = `$${data.money.ct}`;
        if (tBankEl) tBankEl.textContent = `$${data.money.t}`;
        if (ctStatusEl) ctStatusEl.textContent = data.money.ct_status;
        if (tStatusEl) tStatusEl.textContent = data.money.t_status;

        const playerCountEl = get("playerCount");
        if (playerCountEl) {
            const aliveTotal = (data.alive_ct || 0) + (data.alive_t || 0);
            const alive = aliveTotal || data.players.filter(p => p.is_alive).length;
            playerCountEl.textContent = `${alive}/10`;
        }

        const economyEl = get("playerEconomy");
        if (economyEl && data.players && data.players.length > 0) {
            this.renderPlayerEconomy(economyEl, data.players);
        }

        if (data.kill_feed && data.kill_feed.length > 0) {
            this.updateKillFeed(data.kill_feed);
        }

        updateAdvisory(this);

        const parseTimeEl = get("parseTime");
        const avgParseTimeEl = get("avgParseTime");
        const compressionRateEl = get("compressionRate");
        const playersAliveEl = get("playersAlive");
        const latencyEstEl = get("latencyEst");
        const dataRateEl = get("dataRate");
        if (parseTimeEl) parseTimeEl.textContent = this.lastParseMs.toFixed(1) + "ms";
        if (avgParseTimeEl) avgParseTimeEl.textContent = this.avgParseMs.toFixed(1) + "ms";
        if (compressionRateEl) compressionRateEl.textContent = `${this.compressionRate.toFixed(1)}%`;
        if (playersAliveEl) {
            const aliveTotal = (data.alive_ct || 0) + (data.alive_t || 0);
            playersAliveEl.textContent = aliveTotal || data.players.filter(p => p.is_alive).length;
        }
        if (latencyEstEl) {
            if (this.mode === "live") {
                latencyEstEl.textContent = "--:--";
                latencyEstEl.classList.remove("metric-warning");
            } else {
                latencyEstEl.textContent = `${this.demoRemaining.toFixed(1)}s`;
                latencyEstEl.classList.remove("metric-warning");
            }
        }
        const liveLagEl = get("liveLag");
        const demoSpeedEl = get("demoSpeed");
        if (liveLagEl) {
            liveLagEl.textContent = `${this.liveLagSec.toFixed(2)}s`;
            liveLagEl.classList.toggle("metric-warning", this.liveLagSec > 1.0);
        }
        if (demoSpeedEl) {
            demoSpeedEl.textContent = `${this.demoSpeedPct.toFixed(0)}%`;
        }
        if (dataRateEl) dataRateEl.textContent = `${(this.demoDataRateBps / 1024).toFixed(1)}KB/s`;

        const seek = get("playbackSeek");
        const timeLabel = get("playbackTime");
        if (seek && timeLabel && this.demoTotalTime > 0) {
            if (!this.isSeeking) {
                seek.max = String(this.demoTotalTime.toFixed(1));
                seek.value = String(Math.min(this.demoTime, this.demoTotalTime));
            }
            timeLabel.textContent = `${this.formatTime(this.demoTime)} / ${this.formatTime(this.demoTotalTime)}`;
        } else if (timeLabel) {
            timeLabel.textContent = "0:00 / 0:00";
        }

        const now = Date.now();
        const timeDiff = now - this.lastUpdateTime;
        if (timeDiff > 0) {
            const updateRate = (1000 / timeDiff).toFixed(1);
            const updateRateEl = get("updateRate");
            if (updateRateEl) updateRateEl.textContent = updateRate;
        }
        this.lastUpdateTime = now;
    }

    formatTime(totalSeconds) {
        if (!Number.isFinite(totalSeconds)) return "0:00";
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = Math.floor(totalSeconds % 60);
        return `${minutes}:${String(seconds).padStart(2, "0")}`;
    }

    updateKillFeed(kills) {
        const feedElement = this.ui.getElement("killFeed");
        if (!feedElement) return;
        this.clearElement(feedElement);
        kills.slice(-5).reverse().forEach((kill) => {
            const row = document.createElement("div");
            row.className = "kill-event";

            const killer = document.createElement("span");
            killer.className = "kill-killer";
            killer.textContent = kill.killer || "Unknown";

            const weapon = document.createElement("span");
            weapon.className = "kill-weapon";
            weapon.textContent = kill.weapon_emoji || kill.weapon || "Unknown";

            const victim = document.createElement("span");
            victim.className = "kill-victim";
            victim.textContent = kill.victim || "Unknown";

            row.appendChild(killer);
            row.appendChild(weapon);
            row.appendChild(victim);

            if (kill.headshot) {
                const hs = document.createElement("span");
                hs.className = "kill-hs";
                hs.textContent = "HS";
                row.appendChild(hs);
            }

            feedElement.appendChild(row);
        });
    }

    startRenderLoop() {
        const render = () => {
            renderRadar(this);
            requestAnimationFrame(render);
        };
        render();
    }

    setupEventListeners() {
        const mapSelector = this.ui.getElement("mapSelector");
        if (mapSelector) {
            mapSelector.addEventListener("change", (e) => {
                const map = e.target.value;
                this.mapOverride = map;
                this.updateMapOverrideUI();
                this.sendMessage({ type: "set_map_override", map });
            });
        }
        const modeSelector = this.ui.getElement("modeSelector");
        if (modeSelector) {
            modeSelector.addEventListener("change", (e) => {
                this.mode = e.target.value;
                this.ui.updateModeUI(this.mode);
                if (this.mode === "live") {
                    this.selectedDemo = "";
                }
                this.ui.setPlaybackEnabled(this.mode === "manual" && !!this.selectedDemo);
                this.updateDemoStatusUI();
                this.sendMessage({ type: "set_mode", mode: this.mode });
            });
        }
        const demoSelector = this.ui.getElement("demoSelector");
        if (demoSelector) {
            demoSelector.addEventListener("change", (e) => {
                const name = e.target.value;
                if (!name) return;
                this.selectedDemo = name;
                this.demoValid = false;
                this.demoLoading = true;
                this.ui.setPlaybackEnabled(this.mode === "manual" && !!this.selectedDemo);
                this.updateDemoStatusUI();
                this.sendMessage({ type: "select_demo", name });
            });
        }
        const toggleTrails = this.ui.getElement("toggleTrails");
        if (toggleTrails) {
            toggleTrails.addEventListener("change", (e) => {
                this.showTrails = e.target.checked;
            });
        }
        const toggleSmooth = this.ui.getElement("toggleSmooth");
        if (toggleSmooth) {
            toggleSmooth.addEventListener("change", (e) => {
                this.enableSmoothing = e.target.checked;
            });
        }
        const sampling = this.ui.getElement("samplingSelector");
        if (sampling) {
            sampling.addEventListener("change", (e) => {
                const value = parseInt(e.target.value, 10);
                if (!Number.isFinite(value)) return;
                this.msgpackRefreshInterval = value;
                this.sendMessage({ type: "set_sampling", interval: value });
            });
        }
        const samplingToggle = this.ui.getElement("samplingHintToggle");
        const samplingText = this.ui.getElement("samplingHintText");
        if (samplingToggle && samplingText) {
            samplingToggle.addEventListener("click", () => {
                samplingText.classList.toggle("is-open");
            });
        }
        const playBtn = this.ui.getElement("playbackPlay");
        const pauseBtn = this.ui.getElement("playbackPause");
        const backBtn = this.ui.getElement("playbackBack");
        const forwardBtn = this.ui.getElement("playbackForward");
        const speedSelect = this.ui.getElement("playbackSpeed");
        const seek = this.ui.getElement("playbackSeek");
        if (playBtn) {
            playBtn.addEventListener("click", () => {
                this.sendMessage({ type: "playback", action: "play" });
            });
        }
        if (pauseBtn) {
            pauseBtn.addEventListener("click", () => {
                this.sendMessage({ type: "playback", action: "pause" });
            });
        }
        if (backBtn) {
            backBtn.addEventListener("click", () => {
                this.sendSeek(Math.max(0, this.demoTime - 5));
            });
        }
        if (forwardBtn) {
            forwardBtn.addEventListener("click", () => {
                this.sendSeek(this.demoTime + 5);
            });
        }
        if (speedSelect) {
            speedSelect.addEventListener("change", (e) => {
                this.sendMessage({ type: "playback", action: "speed", speed: e.target.value });
            });
        }
        if (seek) {
            seek.addEventListener("input", () => {
                this.isSeeking = true;
            });
            seek.addEventListener("change", () => {
                const value = parseFloat(seek.value || "0");
                this.sendSeek(value);
                this.isSeeking = false;
            });
        }
        const dismissBtn = this.ui.getElement("advisoryDismiss");
        if (dismissBtn) {
            dismissBtn.addEventListener("click", () => {
                this.localStatusMessage = "";
                this.localStatusExpiresAt = 0;
            });
        }
    }

    sendSeek(timeSeconds) {
        if (!Number.isFinite(timeSeconds)) return;
        this.sendMessage({ type: "playback", action: "seek", time: timeSeconds });
    }

    updateSamplingUI() {
        const sampling = this.ui.getElement("samplingSelector");
        if (!sampling) return;
        sampling.value = String(this.msgpackRefreshInterval);
    }

    updateDemoStatusUI() {
        const badge = this.ui.getElement("demoStatusBadge");
        if (!badge) return;
        if (this.mode !== "manual" || !this.selectedDemo) {
            badge.classList.remove("active", "invalid");
            badge.textContent = "Demo";
            return;
        }
        badge.classList.add("active");
        if (this.demoLoading) {
            badge.classList.remove("invalid");
            badge.textContent = "Demo Loading";
            return;
        }
        if (this.demoValid) {
            badge.classList.remove("invalid");
            badge.textContent = "Demo OK";
        } else {
            badge.classList.add("invalid");
            badge.textContent = "Demo Invalid";
        }
    }

    updateMapOverrideUI() {
        const badge = this.ui.getElement("mapOverrideBadge");
        if (!badge) return;
        if (this.mapOverride && this.mapOverride !== "auto") {
            badge.classList.add("active");
            badge.textContent = `Override: ${this.mapOverride}`;
        } else {
            badge.classList.remove("active");
            badge.textContent = "Override";
        }
    }

    loadMapImage(mapName) {
        if (!mapName) return;
        const key = mapName.toLowerCase();
        if (this.mapImages.has(key)) {
            const cached = this.mapImages.get(key);
            if (cached) {
                this.currentMapImage = cached;
                return;
            }
            if (this.mapRetryTimers.has(key)) {
                return;
            }
            this.mapImages.delete(key);
        }
        const candidates = [
            `../maps/boltobserv/de_${key}/radar.png`,
            `../maps/boltobserv/${key}/radar.png`,
        ];
        const attempt = this.mapImageAttempts.get(key) || { index: 0, retries: 0 };
        if (attempt.index >= candidates.length) {
            attempt.index = 0;
        }
        const img = new Image();
        img.onload = () => {
            this.mapImages.set(key, img);
            if (this.currentMap === mapName) {
                this.currentMapImage = img;
            }
            this.mapImageAttempts.delete(key);
            const timer = this.mapRetryTimers.get(key);
            if (timer) {
                clearTimeout(timer);
                this.mapRetryTimers.delete(key);
            }
            if (this.localStatusMessage && this.localStatusExpiresAt === Number.POSITIVE_INFINITY) {
                this.localStatusMessage = "";
                this.localStatusExpiresAt = 0;
            }
        };
        img.onerror = () => {
            attempt.index += 1;
            if (attempt.index < candidates.length) {
                this.mapImageAttempts.set(key, attempt);
                this.loadMapImage(mapName);
                return;
            }
            attempt.retries += 1;
            attempt.index = 0;
            this.mapImageAttempts.set(key, attempt);
            if (!this.mapRetryTimers.has(key)) {
                const delay = Math.min(30000, 3000 * attempt.retries);
                const timer = setTimeout(() => {
                    this.mapRetryTimers.delete(key);
                    this.loadMapImage(mapName);
                }, delay);
                this.mapRetryTimers.set(key, timer);
            }
            this.mapImages.set(key, null);
            if (this.currentMap === mapName) {
                this.currentMapImage = null;
            }
            this.localStatusMessage = `Map texture missing for ${mapName}`;
            this.localStatusLevel = "warning";
            this.localStatusExpiresAt = Number.POSITIVE_INFINITY;
            console.warn(`Map image not found for ${mapName}`);
        };
        img.src = candidates[attempt.index];
    }

    loadClientConfig() {
        fetch("../config.json")
            .then((response) => response.ok ? response.json() : null)
            .then((config) => {
                if (!config || !config.client) return;
                const client = config.client;
                if (typeof client.enable_trails === "boolean") {
                    this.showTrails = client.enable_trails;
                    const toggle = document.getElementById("toggleTrails");
                    if (toggle) toggle.checked = this.showTrails;
                }
                if (typeof client.enable_smoothing === "boolean") {
                    this.enableSmoothing = client.enable_smoothing;
                    const toggle = document.getElementById("toggleSmooth");
                    if (toggle) toggle.checked = this.enableSmoothing;
                }
            })
            .catch(() => {});
    }
}

window.addEventListener("load", () => {
    new CS2BroadcasterClient();
});
