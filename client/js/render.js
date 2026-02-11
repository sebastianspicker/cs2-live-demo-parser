export function updateTrails(client, state) {
    if (!client.showTrails) return;
    if (!state || !state.players) return;
    const currentKeys = new Set();
    state.players.forEach(player => {
        const key = _playerKey(player);
        currentKeys.add(key);
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
    client.trails.forEach((_, key) => {
        if (!currentKeys.has(key)) client.trails.delete(key);
    });
}

function _playerKey(p) {
    return `${p.id ?? ""}_${p.name ?? ""}`;
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
    const lastByKey = new Map();
    client.lastState.players.forEach(player => {
        lastByKey.set(_playerKey(player), player);
    });
    return client.currentState.players.map(player => {
        const prev = lastByKey.get(_playerKey(player));
        if (!prev) return player;
        const x = prev.x + (player.x - prev.x) * alpha;
        const y = prev.y + (player.y - prev.y) * alpha;
        return { ...player, x, y };
    });
}

export function renderRadar(client) {
    if (!client.gameState || !client.mapConfig || !client.ctx || !client.canvas) return;

    const width = client.canvas.width;
    const height = client.canvas.height;
    const bounds = client.mapConfig.world_bounds;
    const transform = client.mapConfig.world_transform;
    const fallbackSize = 1024;
    let mapWidth = bounds ? (bounds.max_x - bounds.min_x) : (client.mapConfig.width || fallbackSize);
    let mapHeight = bounds ? (bounds.max_y - bounds.min_y) : (client.mapConfig.height || fallbackSize);
    if (!Number.isFinite(mapWidth) || mapWidth <= 0) mapWidth = fallbackSize;
    if (!Number.isFinite(mapHeight) || mapHeight <= 0) mapHeight = fallbackSize;

    const viewRotation = (client.radarSettings && client.radarSettings.viewRotation) || 0;
    if (viewRotation) {
        client.ctx.save();
        client.ctx.translate(width / 2, height / 2);
        client.ctx.rotate((viewRotation * Math.PI) / 180);
        client.ctx.translate(-width / 2, -height / 2);
    }
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
            if (mapTeamFilter !== "all" && (mapTeamFilter === "t" ? trailEntry.team !== "T" : trailEntry.team !== "CT")) return;
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
    const settings = client.radarSettings || {};
    const dotSizeMult = typeof settings.dotSize === "number" && Number.isFinite(settings.dotSize) ? settings.dotSize : 1;
    const showAllyNames = settings.showAllyNames !== false && !!settings.showAllyNames;
    const showEnemyNames = settings.showEnemyNames !== false;
    const showViewCones = !!settings.showViewCones;
    const mapTeamFilter = settings.mapTeamFilter === "t" || settings.mapTeamFilter === "ct" ? settings.mapTeamFilter : "all";
    let players = getInterpolatedPlayers(client);
    if (mapTeamFilter !== "all") {
        players = players.filter(p => p.team === (mapTeamFilter === "t" ? "T" : "CT"));
    }

    if (!client.deadLastPosition) client.deadLastPosition = new Map();
    const playerKey = _playerKey;
    players.forEach(player => {
        const key = playerKey(player);
        if (player.is_alive) {
            client.deadLastPosition.delete(key);
        } else {
            client.deadLastPosition.set(key, { x: player.x, y: player.y });
        }
    });

    players.forEach(player => {
        const key = playerKey(player);
        const deadPos = client.deadLastPosition.get(key);
        const effX = player.is_alive ? player.x : (deadPos ? deadPos.x : player.x);
        const effY = player.is_alive ? player.y : (deadPos ? deadPos.y : player.y);
        const screen = toScreen(effX, effY);
        const screenX = screen.x;
        const screenY = screen.y;

        let radius = 6 * dotSizeMult;
        let zNormalized = null;
        if (zRange) {
            const minZ = zRange.min;
            const maxZ = zRange.max;
            if (typeof minZ === "number" && typeof maxZ === "number" && maxZ > minZ) {
                const z = typeof player.z === "number" ? player.z : 0;
                const t = Math.max(0, Math.min(1, (z - minZ) / (maxZ - minZ)));
                zNormalized = t;
                radius = (4 + t * 4) * dotSizeMult;
            }
        }

        const yawDeg = typeof player.yaw === "number" ? player.yaw : 0;
        const rotationRad = ((270 - yawDeg) * Math.PI) / 180;

        if (player.is_alive) {
            client.ctx.save();
            client.ctx.translate(screenX, screenY);
            client.ctx.rotate(rotationRad);
            if (showViewCones) {
                const coneR = radius * 1.8;
                const coneAngle = (22 * Math.PI) / 180;
                client.ctx.fillStyle = "rgba(255, 255, 255, 0.25)";
                client.ctx.beginPath();
                client.ctx.moveTo(0, 0);
                client.ctx.arc(0, 0, coneR, -coneAngle, coneAngle);
                client.ctx.closePath();
                client.ctx.fill();
            }
            client.ctx.fillStyle = player.team === "CT" ? "#4a9eff" : "#ffb700";
            client.ctx.beginPath();
            client.ctx.moveTo(0, -radius);
            client.ctx.lineTo(-radius * 0.65, radius * 0.5);
            client.ctx.lineTo(radius * 0.65, radius * 0.5);
            client.ctx.closePath();
            client.ctx.fill();
            client.ctx.restore();
        } else {
            client.ctx.globalAlpha = 0.8;
            client.ctx.save();
            client.ctx.translate(screenX, screenY);
            client.ctx.rotate(rotationRad);
            client.ctx.fillStyle = player.team === "CT" ? "#4a9eff" : "#ffb700";
            client.ctx.beginPath();
            client.ctx.moveTo(0, -radius);
            client.ctx.lineTo(-radius * 0.65, radius * 0.5);
            client.ctx.lineTo(radius * 0.65, radius * 0.5);
            client.ctx.closePath();
            client.ctx.fill();
            client.ctx.restore();
            client.ctx.globalAlpha = 1;
            client.ctx.strokeStyle = "#ff3860";
            client.ctx.lineWidth = 2;
            const xr = radius * 0.8;
            client.ctx.beginPath();
            client.ctx.moveTo(screenX - xr, screenY - xr);
            client.ctx.lineTo(screenX + xr, screenY + xr);
            client.ctx.moveTo(screenX + xr, screenY - xr);
            client.ctx.lineTo(screenX - xr, screenY + xr);
            client.ctx.stroke();
        }

        if (zNormalized !== null && player.is_alive) {
            client.ctx.save();
            client.ctx.translate(screenX, screenY);
            if (zNormalized > 0.66) {
                client.ctx.strokeStyle = "rgba(0, 212, 255, 0.6)";
                client.ctx.lineWidth = 2;
                client.ctx.beginPath();
                client.ctx.arc(0, 0, radius + 3, 0, Math.PI * 2);
                client.ctx.stroke();
            } else if (zNormalized < 0.33) {
                client.ctx.strokeStyle = "rgba(255, 255, 255, 0.3)";
                client.ctx.lineWidth = 1;
                client.ctx.setLineDash([2, 2]);
                client.ctx.beginPath();
                client.ctx.arc(0, 0, radius + 2, 0, Math.PI * 2);
                client.ctx.stroke();
                client.ctx.setLineDash([]);
            }
            client.ctx.restore();
        }

        const states = client.playerStates.get(player.name) || {};
        if (player.is_alive) {
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
        }

        const showName = (player.team === "CT" && showAllyNames) || (player.team === "T" && showEnemyNames);
        if (showName) {
            client.ctx.fillStyle = "#ffffff";
            client.ctx.font = "11px Arial";
            client.ctx.textAlign = "center";
            client.ctx.fillText(player.name, screenX, screenY + 18);
        }
    });

    const showBombOnMap = (client.radarSettings && client.radarSettings.showBombOnMap) !== false;
    const bomb = client.gameState.bomb;
    if (showBombOnMap && bomb && (bomb.planted || bomb.position || bomb.planter)) {
        let bombPos = bomb.position;
        if (!bombPos && bomb.planter && Array.isArray(client.gameState.players)) {
            const carrier = client.gameState.players.find(p => p.name === bomb.planter);
            if (carrier) {
                bombPos = { x: carrier.x, y: carrier.y };
            }
        }
        if (bombPos) {
            const screen = toScreen(bombPos.x, bombPos.y);
            const b = client.radarSettings && client.radarSettings.bombSize;
            const bombSizeMult = typeof b === "number" && Number.isFinite(b) ? b : 0.5;
            const bombRadius = 7 * bombSizeMult;
            client.ctx.fillStyle = "#ff3860";
            client.ctx.beginPath();
            client.ctx.arc(screen.x, screen.y, bombRadius, 0, Math.PI * 2);
            client.ctx.fill();
            client.ctx.fillStyle = "#ffffff";
            client.ctx.font = "10px Arial";
            client.ctx.textAlign = "center";
            client.ctx.fillText("C4", screen.x, screen.y + 3);
        }
    }
    if (viewRotation) {
        client.ctx.restore();
    }
}
