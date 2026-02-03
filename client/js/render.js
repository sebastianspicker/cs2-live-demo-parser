export function updateTrails(client, state) {
    if (!client.showTrails) return;
    if (!state || !state.players) return;
    state.players.forEach(player => {
        const key = player.id || player.name;
        if (!client.trails.has(key)) {
            client.trails.set(key, { points: [], team: player.team || "UNK" });
        }
        const trailEntry = client.trails.get(key);
        trailEntry.team = player.team || trailEntry.team;
        trailEntry.points.push({ x: player.x, y: player.y, t: Date.now() });
        if (trailEntry.points.length > 12) {
            trailEntry.points.shift();
        }
    });
}

export function getInterpolatedPlayers(client) {
    if (!client.currentState || !client.currentState.players) {
        return [];
    }
    if (!client.enableSmoothing) {
        return client.currentState.players;
    }
    if (!client.lastState || !client.lastState.players) {
        return client.currentState.players;
    }
    const now = Date.now();
    const alpha = Math.min(1, (now - client.lastUpdateReceived) / client.smoothIntervalMs);
    const lastById = new Map();
    client.lastState.players.forEach(player => {
        lastById.set(player.id, player);
    });
    return client.currentState.players.map(player => {
        const prev = lastById.get(player.id);
        if (!prev) return player;
        const x = prev.x + (player.x - prev.x) * alpha;
        const y = prev.y + (player.y - prev.y) * alpha;
        return { ...player, x, y };
    });
}

export function renderRadar(client) {
    if (!client.gameState || !client.mapConfig) return;

    const width = client.canvas.width;
    const height = client.canvas.height;
    const bounds = client.mapConfig.world_bounds;
    const transform = client.mapConfig.world_transform;
    const fallbackSize = 1024;
    const mapWidth = bounds ? (bounds.max_x - bounds.min_x) : (client.mapConfig.width || fallbackSize);
    const mapHeight = bounds ? (bounds.max_y - bounds.min_y) : (client.mapConfig.height || fallbackSize);

    client.ctx.fillStyle = "#1a1a1a";
    client.ctx.fillRect(0, 0, width, height);
    if (client.currentMapImage) {
        client.ctx.globalAlpha = 0.85;
        client.ctx.drawImage(client.currentMapImage, 0, 0, width, height);
        client.ctx.globalAlpha = 1;
    }

    client.ctx.strokeStyle = "rgba(0, 212, 255, 0.1)";
    client.ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
        const x = (i / 10) * width;
        const y = (i / 10) * height;
        client.ctx.beginPath();
        client.ctx.moveTo(x, 0);
        client.ctx.lineTo(x, height);
        client.ctx.stroke();
        client.ctx.beginPath();
        client.ctx.moveTo(0, y);
        client.ctx.lineTo(width, y);
        client.ctx.stroke();
    }

    const toScreen = (x, y) => {
        if (bounds && transform) {
            let tx = x;
            let ty = y;
            if (transform.flip_x) {
                tx = bounds.max_x + bounds.min_x - tx;
            }
            if (transform.flip_y) {
                ty = bounds.max_y + bounds.min_y - ty;
            }
            if (transform.rotate_deg) {
                const radians = (transform.rotate_deg * Math.PI) / 180;
                const cx = (bounds.min_x + bounds.max_x) / 2;
                const cy = (bounds.min_y + bounds.max_y) / 2;
                const dx = tx - cx;
                const dy = ty - cy;
                const cos = Math.cos(radians);
                const sin = Math.sin(radians);
                const rx = dx * cos - dy * sin;
                const ry = dx * sin + dy * cos;
                tx = cx + rx;
                ty = cy + ry;
            }
            return {
                x: ((tx - bounds.min_x) / mapWidth) * width,
                y: ((ty - bounds.min_y) / mapHeight) * height,
            };
        }
        if (bounds) {
            return {
                x: ((x - bounds.min_x) / mapWidth) * width,
                y: ((y - bounds.min_y) / mapHeight) * height,
            };
        }
        return {
            x: ((x + mapWidth / 2) / mapWidth) * width,
            y: ((y + mapHeight / 2) / mapHeight) * height,
        };
    };

    const now = Date.now();
    client.utilityEvents.forEach(event => {
        if (event.expiresAt <= now) return;
        const screen = toScreen(event.x, event.y);
        const colors = {
            hegrenade_detonate: "#ff3860",
            flashbang_detonate: "#f5f0b4",
            smokegrenade_detonate: "#9aa0a6",
            smokegrenade_expired: "#61676d",
            molotov_detonate: "#ff9f43",
            decoy_detonate: "#a29bfe",
        };
        client.ctx.fillStyle = colors[event.type] || "#ffffff";
        client.ctx.beginPath();
        client.ctx.arc(screen.x, screen.y, 5, 0, Math.PI * 2);
        client.ctx.fill();
    });

    if (client.showTrails) {
        client.trails.forEach((trailEntry) => {
            const trail = trailEntry.points;
            if (trail.length < 2) return;
            const baseColor = trailEntry.team === "CT" ? [74, 158, 255] : trailEntry.team === "T" ? [255, 183, 0] : [200, 200, 200];
            client.ctx.lineWidth = 2;
            client.ctx.beginPath();
            trail.forEach((point, index) => {
                const screen = toScreen(point.x, point.y);
                const alpha = (index + 1) / trail.length;
                client.ctx.strokeStyle = `rgba(${baseColor[0]}, ${baseColor[1]}, ${baseColor[2]}, ${0.1 + alpha * 0.4})`;
                if (index === 0) {
                    client.ctx.moveTo(screen.x, screen.y);
                } else {
                    client.ctx.lineTo(screen.x, screen.y);
                }
            });
            client.ctx.stroke();
        });
    }

    const zRange = client.mapConfig && client.mapConfig.z_range ? client.mapConfig.z_range : null;
    getInterpolatedPlayers(client).forEach(player => {
        const screen = toScreen(player.x, player.y);
        const screenX = screen.x;
        const screenY = screen.y;

        client.ctx.fillStyle = player.team === "CT" ? "#4a9eff" : "#ffb700";
        client.ctx.beginPath();
        let radius = 6;
        let zNormalized = null;
        if (zRange) {
            const minZ = zRange.min;
            const maxZ = zRange.max;
            if (typeof minZ === "number" && typeof maxZ === "number" && maxZ > minZ) {
                const z = typeof player.z === "number" ? player.z : 0;
                const t = Math.max(0, Math.min(1, (z - minZ) / (maxZ - minZ)));
                zNormalized = t;
                radius = 4 + t * 4;
            }
        }
        client.ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
        client.ctx.fill();

        if (zNormalized !== null) {
            if (zNormalized > 0.66) {
                client.ctx.strokeStyle = "rgba(0, 212, 255, 0.6)";
                client.ctx.lineWidth = 2;
                client.ctx.beginPath();
                client.ctx.arc(screenX, screenY, radius + 3, 0, Math.PI * 2);
                client.ctx.stroke();
            } else if (zNormalized < 0.33) {
                client.ctx.strokeStyle = "rgba(255, 255, 255, 0.3)";
                client.ctx.lineWidth = 1;
                client.ctx.setLineDash([2, 2]);
                client.ctx.beginPath();
                client.ctx.arc(screenX, screenY, radius + 2, 0, Math.PI * 2);
                client.ctx.stroke();
                client.ctx.setLineDash([]);
            }
        }

        const states = client.playerStates.get(player.name) || {};
        if (states.flash && states.flash > now) {
            client.ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
            client.ctx.lineWidth = 2;
            client.ctx.beginPath();
            client.ctx.arc(screenX, screenY, radius + 3, 0, Math.PI * 2);
            client.ctx.stroke();
        }
        if (states.shoot && states.shoot > now) {
            client.ctx.strokeStyle = "rgba(255, 215, 0, 0.9)";
            client.ctx.lineWidth = 2;
            client.ctx.beginPath();
            client.ctx.arc(screenX, screenY, radius + 5, 0, Math.PI * 2);
            client.ctx.stroke();
        }
        if (states.hurt && states.hurt > now) {
            client.ctx.strokeStyle = "rgba(255, 56, 96, 0.9)";
            client.ctx.lineWidth = 2;
            client.ctx.beginPath();
            client.ctx.arc(screenX, screenY, radius + 1, 0, Math.PI * 2);
            client.ctx.stroke();
        }

        if (!player.is_alive) {
            client.ctx.fillStyle = "#ff3860";
            client.ctx.fillRect(screenX - 10, screenY - 10, 20, 3);
        }

        client.ctx.fillStyle = "#ffffff";
        client.ctx.font = "11px Arial";
        client.ctx.textAlign = "center";
        client.ctx.fillText(player.name, screenX, screenY + 18);
    });

    const bomb = client.gameState.bomb;
    if (bomb && (bomb.planted || bomb.position || bomb.planter)) {
        let bombPos = bomb.position;
        if (!bombPos && bomb.planter && client.gameState.players) {
            const carrier = client.gameState.players.find(p => p.name === bomb.planter);
            if (carrier) {
                bombPos = { x: carrier.x, y: carrier.y };
            }
        }
        if (bombPos) {
            const screen = toScreen(bombPos.x, bombPos.y);
            client.ctx.fillStyle = "#ff3860";
            client.ctx.beginPath();
            client.ctx.arc(screen.x, screen.y, 7, 0, Math.PI * 2);
            client.ctx.fill();
            client.ctx.fillStyle = "#ffffff";
            client.ctx.font = "10px Arial";
            client.ctx.textAlign = "center";
            client.ctx.fillText("C4", screen.x, screen.y + 3);
        }
    }
}
