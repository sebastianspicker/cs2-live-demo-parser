import { _playerKey } from "./render.js";

function playerKeyFromName(client, playerName) {
    if (!playerName) return "";
    const players = client.currentState?.players;
    if (Array.isArray(players)) {
        const p = players.find((x) => x && x.name === playerName);
        if (p) return _playerKey(p);
    }
    return String(playerName);
}

export function processEvents(client, events) {
    const now = Date.now();
    const ttlMap = {
        hegrenade_detonate: 1200,
        flashbang_detonate: 800,
        smokegrenade_detonate: 18000,
        smokegrenade_expired: 1500,
        molotov_detonate: 7000,
        decoy_detonate: 3000,
        weapon_fire: 250,
        player_hurt: 600,
        player_blind: 1500,
        bomb_planted: 4000,
        bomb_defused: 4000,
        bomb_exploded: 4000,
    };

    events.forEach((event) => {
        const type = event.type;
        if (!type || !(type in ttlMap)) return;
        if (type.endsWith("detonate") || type.endsWith("expired")) {
            if (typeof event.x === "number" && typeof event.y === "number") {
                client.utilityEvents.push({
                    type,
                    x: event.x,
                    y: event.y,
                    z: event.z || 0,
                    expiresAt: now + ttlMap[type],
                });
            }
            return;
        }
        if (type === "weapon_fire") {
            setPlayerState(client, playerKeyFromName(client, event.player), "shoot", now + ttlMap[type]);
        } else if (type === "player_hurt") {
            setPlayerState(client, playerKeyFromName(client, event.victim), "hurt", now + ttlMap[type]);
        } else if (type === "player_blind") {
            setPlayerState(client, playerKeyFromName(client, event.player), "flash", now + ttlMap[type]);
        } else if (type.startsWith("bomb_")) {
            setAdvisory(client, type);
        }
    });

    client.utilityEvents = client.utilityEvents.filter(e => e.expiresAt > now);
    cleanupPlayerStates(client, now);
}

export function setPlayerState(client, playerKey, state, expiresAt) {
    if (!playerKey) return;
    if (!client.playerStates.has(playerKey)) {
        client.playerStates.set(playerKey, {});
    }
    const entry = client.playerStates.get(playerKey);
    entry[state] = expiresAt;
}

export function cleanupPlayerStates(client, now) {
    client.playerStates.forEach((entry, key) => {
        const cleaned = {};
        Object.keys(entry).forEach((state) => {
            if (entry[state] > now) {
                cleaned[state] = entry[state];
            }
        });
        if (Object.keys(cleaned).length === 0) {
            client.playerStates.delete(key);
        } else {
            client.playerStates.set(key, cleaned);
        }
    });
}

export function setAdvisory(client, type) {
    const now = Date.now();
    const messages = {
        bomb_planted: "💣 Bomb planted",
        bomb_defused: "🛡️ Bomb defused",
        bomb_exploded: "💥 Bomb exploded",
    };
    client.advisory = messages[type] || null;
    client.advisoryExpiresAt = now + 4000;
}

export function updateAdvisory(client) {
    const banner = document.getElementById("advisoryBanner");
    const textEl = document.getElementById("advisoryText");
    const dismissBtn = document.getElementById("advisoryDismiss");
    if (!banner) return;
    const now = Date.now();
    let text = "";
    let active = false;
    let statusClass = "";
    if (client.statusMessage && now < client.statusExpiresAt) {
        text = client.statusMessage;
        active = true;
        statusClass = `status-${client.statusLevel || "info"}`;
    } else if (client.statusMessage && client.statusExpiresAt === Number.POSITIVE_INFINITY) {
        text = client.statusMessage;
        active = true;
        statusClass = `status-${client.statusLevel || "info"}`;
    } else if (client.localStatusMessage && now < client.localStatusExpiresAt) {
        text = client.localStatusMessage;
        active = true;
        statusClass = `status-${client.localStatusLevel || "info"}`;
    }
    if (!active && client.advisory && now < client.advisoryExpiresAt) {
        text = client.advisory;
        active = true;
    } else if (client.gameState && Array.isArray(client.gameState.players)) {
        const ctAlive = client.gameState.players.filter(p => p.team === "CT" && p.is_alive).length;
        const tAlive = client.gameState.players.filter(p => p.team === "T" && p.is_alive).length;
        if (ctAlive === 1 && tAlive > 1) {
            text = "🧯 CT Sole Survivor";
            active = true;
        } else if (tAlive === 1 && ctAlive > 1) {
            text = "🔥 T Sole Survivor";
            active = true;
        }
    }
    if (textEl) {
        textEl.textContent = text;
    } else {
        banner.textContent = text;
    }
    banner.style.display = active ? "flex" : "none";
    if (dismissBtn) {
        dismissBtn.style.display = active ? "inline-flex" : "none";
    }
    const allowedStatusClasses = ["status-info", "status-warning", "status-error"];
    banner.classList.remove(...allowedStatusClasses);
    if (statusClass && allowedStatusClasses.includes(statusClass)) {
        banner.classList.add(statusClass);
    }

    const safetyBadge = document.getElementById("mapSafetyBadge");
    if (safetyBadge) {
        if (client.boundsSafe === false) {
            safetyBadge.classList.add("active");
            safetyBadge.textContent = "Bounds Missing";
        } else {
            safetyBadge.classList.remove("active");
            safetyBadge.textContent = "Map";
        }
    }
}
