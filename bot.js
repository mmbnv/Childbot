const mineflayer = require('mineflayer');
const http = require('http');
const vec3 = require('vec3');

const BOT_NAME = 'ChildBot';

const bot = mineflayer.createBot({
  host: 'localhost',
  port: 63696,
  username: BOT_NAME,
  version: '1.20.1'
});

let chatQueue = [];
let lastDamageTime = 0;

let playerActions = [];
const MAX_RECORDED = 100;
const MIN_RECORD_INTERVAL_MS = 800;
const MIN_MOVEMENT_DIST = 0.5;
let lastRecordTime = {};
let lastRecordPos = {};

let soundLog = [];
const MAX_SOUNDS = 50;

const HOSTILE = ['zombie','skeleton','creeper','spider','enderman','witch','slime','phantom','drowned','husk','stray','pillager','vindicator','ravager'];
const PASSIVE = ['cow','pig','sheep','chicken','rabbit','horse','villager'];

bot.on('spawn', () => {
  console.log('=================================');
  console.log('Бот в мире!');
  console.log('=================================');
  bot.chat('Привет! Я тут.');
});

bot.on('death', () => {
  console.log('💀 Бот погиб! Возрождаюсь...');
  try { bot.chat('Ой, я умер...'); } catch(e) {}
  setTimeout(() => {
    try { bot.respawn(); console.log('♻️  Отправлен respawn'); }
    catch(e) { console.log('respawn ошибка:', e.message); }
  }, 2000);
});

bot.on('respawn', () => { console.log('♻️  Возрождён!'); });

bot.on('chat', (username, message) => {
  if (username === BOT_NAME || username === bot.username) return;
  console.log(`📨 ${username}: ${message}`);
  chatQueue.push({ name: username, text: message, time: Date.now() });
  if (chatQueue.length > 50) chatQueue.shift();
});

bot.on('soundEffectHeard', (soundName, position, volume) => {
  soundLog.push({
    sound: soundName,
    x: position.x, y: position.y, z: position.z,
    volume: volume, time: Date.now()
  });
  if (soundLog.length > MAX_SOUNDS) soundLog.shift();
});

bot.on('hardcodedSoundEffectHeard', (soundId, position, volume) => {
  soundLog.push({
    sound: 'id_' + soundId,
    x: position.x, y: position.y, z: position.z,
    volume: volume, time: Date.now()
  });
  if (soundLog.length > MAX_SOUNDS) soundLog.shift();
});

bot.on('entityHurt', (entity) => {
  if (entity === bot.entity) {
    lastDamageTime = Date.now();
    console.log('💥 Урон!');
  }
});

bot.on('entitySwingArm', (entity) => {
  if (!entity || !entity.username) return;
  if (entity.username === bot.username) return;
  if (entity.username === BOT_NAME) return;

  const name = entity.username;
  const pos = entity.position;
  const now = Date.now();

  if (lastRecordTime[name] && now - lastRecordTime[name] < MIN_RECORD_INTERVAL_MS) return;
  const lastPos = lastRecordPos[name];
  if (lastPos) {
    const dx = pos.x - lastPos.x, dz = pos.z - lastPos.z;
    if (Math.sqrt(dx*dx + dz*dz) < MIN_MOVEMENT_DIST) return;
  }

  let targetBlock = null;
  const yaw = entity.yaw, pitch = entity.pitch;
  for (let step = 1; step < 6; step += 0.5) {
    const dx = -Math.sin(yaw) * Math.cos(pitch) * step;
    const dy = Math.sin(pitch) * step;
    const dz = -Math.cos(yaw) * Math.cos(pitch) * step;
    const probe = pos.offset(dx, dy, dz).floored();
    const b = bot.blockAt(probe);
    if (b && b.name !== 'air') {
      targetBlock = { name: b.name, x: probe.x, y: probe.y, z: probe.z };
      break;
    }
  }

  playerActions.push({
    player: name, action: 'swing',
    x: pos.x, y: pos.y, z: pos.z,
    yaw: yaw, pitch: pitch,
    target: targetBlock, time: now
  });
  if (playerActions.length > MAX_RECORDED) playerActions.shift();

  lastRecordTime[name] = now;
  lastRecordPos[name] = { x: pos.x, y: pos.y, z: pos.z };

  const targetStr = targetBlock ? ` → ${targetBlock.name}` : '';
  console.log(`📝 Записано: swing @ (${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)})${targetStr} [всего ${playerActions.length}]`);
});

bot.on('error', (err) => console.log('Ошибка:', err.message));
bot.on('kicked', (r) => console.log('Кикнут:', r));

// ============ УТИЛИТЫ ============

function findNearestPlayer() {
  const pos = bot.entity ? bot.entity.position : null;
  if (!pos) return null;
  let nearest = null, nd = Infinity;
  for (const name in bot.players) {
    if (name === BOT_NAME || name === bot.username) continue;
    const p = bot.players[name];
    if (!p.entity) continue;
    const dx = p.entity.position.x - pos.x;
    const dz = p.entity.position.z - pos.z;
    const d = Math.sqrt(dx*dx + dz*dz);
    if (d < nd) { nd = d; nearest = p; }
  }
  return nearest;
}

function findNearestHostile() {
  const pos = bot.entity.position;
  let nearest = null, nd = Infinity;
  for (const id in bot.entities) {
    const e = bot.entities[id];
    if (e === bot.entity || !e.position || !e.name) continue;
    if (!HOSTILE.includes(e.name)) continue;
    const d = e.position.distanceTo(pos);
    if (d < nd) { nd = d; nearest = { name: e.name, distance: d, x: e.position.x, y: e.position.y, z: e.position.z, entity: e }; }
  }
  return nearest;
}

function findNearestPassive() {
  const pos = bot.entity.position;
  let nearest = null, nd = Infinity;
  for (const id in bot.entities) {
    const e = bot.entities[id];
    if (e === bot.entity || !e.position || !e.name) continue;
    if (!PASSIVE.includes(e.name)) continue;
    const d = e.position.distanceTo(pos);
    if (d < nd) { nd = d; nearest = e; }
  }
  return nearest;
}

function nearbyBlocks(radius = 6) {
  const pos = bot.entity.position;
  const found = [];
  for (let x = -radius; x <= radius; x++) {
    for (let y = -3; y <= 3; y++) {
      for (let z = -radius; z <= radius; z++) {
        const p = pos.offset(x, y, z);
        const b = bot.blockAt(p);
        if (b && b.name !== 'air') {
          found.push({ name: b.name, x: p.x, y: p.y, z: p.z,
            distance: Math.sqrt(x*x+y*y+z*z), diggable: b.diggable });
        }
      }
    }
  }
  found.sort((a,b) => a.distance - b.distance);
  return found.slice(0, 30);
}

function visibleBlocks(radius = 16) {
  const pos = bot.entity.position;
  const yaw = bot.entity.yaw;
  const pitch = bot.entity.pitch;
  const found = [];
  const dirX = -Math.sin(yaw) * Math.cos(pitch);
  const dirZ = -Math.cos(yaw) * Math.cos(pitch);
  const dirY = Math.sin(pitch);
  for (let x = -radius; x <= radius; x++) {
    for (let y = -4; y <= 4; y++) {
      for (let z = -radius; z <= radius; z++) {
        const p = pos.offset(x, y, z);
        const b = bot.blockAt(p);
        if (!b || b.name === 'air') continue;
        const d = Math.sqrt(x*x+y*y+z*z);
        if (d > radius || d < 0.5) continue;
        const nx = x/d, ny = y/d, nz = z/d;
        const dot = nx*dirX + ny*dirY + nz*dirZ;
        if (dot < 0.3) continue;
        found.push({ name: b.name, x: p.x, y: p.y, z: p.z, distance: d });
      }
    }
  }
  found.sort((a,b) => a.distance - b.distance);
  return found.slice(0, 20);
}

function inventoryInfo() {
  return bot.inventory.items().map(i => ({ name: i.name, count: i.count, slot: i.slot }));
}

function armorInfo() {
  const slots = {
    head: bot.inventory.slots[5], torso: bot.inventory.slots[6],
    legs: bot.inventory.slots[7], feet: bot.inventory.slots[8]
  };
  const out = {};
  for (const k in slots) out[k] = slots[k] ? slots[k].name : null;
  return out;
}

function isInPit() {
  if (!bot.entity) return false;
  const bp = bot.entity.position;
  const feet = bp.floored();
  const above = bot.blockAt(feet.offset(0, 2, 0));
  const wallN = bot.blockAt(feet.offset(0, 0, -1));
  const wallS = bot.blockAt(feet.offset(0, 0, 1));
  const wallE = bot.blockAt(feet.offset(1, 0, 0));
  const wallW = bot.blockAt(feet.offset(-1, 0, 0));
  const walls = [wallN, wallS, wallE, wallW].filter(b => b && b.boundingBox === 'block').length;
  const ceiling = above && above.boundingBox === 'block';
  return walls >= 3 && ceiling;
}

function hasSkyAbove() {
  if (!bot.entity) return true;
  const bp = bot.entity.position;
  for (let y = 2; y < 20; y++) {
    const b = bot.blockAt(bp.offset(0, y, 0));
    if (b && b.boundingBox === 'block') return false;
  }
  return true;
}

async function goTo(x, z, tolerance = 1.0, timeout = 10000) {
  const start = Date.now();
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      if (Date.now() - start > timeout) {
        clearInterval(interval);
        ['forward','back','left','right','jump','sprint'].forEach(k => bot.setControlState(k, false));
        resolve(false); return;
      }
      if (!bot.entity) { clearInterval(interval); resolve(false); return; }
      const bp = bot.entity.position;
      const dx = x - bp.x, dz = z - bp.z;
      const dist = Math.sqrt(dx*dx + dz*dz);
      if (dist < tolerance) {
        clearInterval(interval);
        ['forward','back','left','right','jump','sprint'].forEach(k => bot.setControlState(k, false));
        resolve(true); return;
      }
      const targetYaw = Math.atan2(-dx, -dz);
      const curYaw = bot.entity.yaw;
      let dYaw = targetYaw - curYaw;
      while (dYaw > Math.PI) dYaw -= Math.PI * 2;
      while (dYaw < -Math.PI) dYaw += Math.PI * 2;
      bot.look(curYaw + dYaw * 0.3, 0, false);

      const len = Math.sqrt(dx*dx + dz*dz);
      const dirX = dx/len, dirZ = dz/len;
      const fp = bp.offset(dirX, 0, dirZ).floored();
      const low = bot.blockAt(fp);
      const high = bot.blockAt(fp.offset(0,1,0));
      const blocked = low && low.boundingBox === 'block';
      const tooHigh = high && high.boundingBox === 'block';
      if (blocked && !tooHigh) {
        bot.setControlState('jump', true);
        bot.setControlState('forward', true);
      } else if (blocked && tooHigh) {
        const side = Math.random() < 0.5 ? 'left' : 'right';
        bot.setControlState(side, true);
        setTimeout(() => bot.setControlState(side, false), 300);
      } else {
        bot.setControlState('forward', true);
      }
    }, 100);
  });
}

async function smoothLookAt(x, y, z, steps = 5) {
  if (!bot.entity) return;
  const bp = bot.entity.position;
  const dx = x - bp.x, dy = y - (bp.y + 1.6), dz = z - bp.z;
  const targetYaw = Math.atan2(-dx, -dz);
  const targetPitch = Math.atan2(dy, Math.sqrt(dx*dx + dz*dz));
  const startYaw = bot.entity.yaw, startPitch = bot.entity.pitch;
  let dYaw = targetYaw - startYaw;
  while (dYaw > Math.PI) dYaw -= Math.PI * 2;
  while (dYaw < -Math.PI) dYaw += Math.PI * 2;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    bot.look(startYaw + dYaw * t, startPitch + (targetPitch - startPitch) * t, false);
    await new Promise(r => setTimeout(r, 40));
  }
}

async function mimicPlayerAction(index) {
  if (index < 0) index = playerActions.length + index;
  if (index < 0 || index >= playerActions.length) {
    return { ok: false, reason: 'no_action', total: playerActions.length };
  }
  const a = playerActions[index];
  const arrived = await goTo(a.x, a.z, 1.5, 8000);
  if (!arrived) return { ok: false, reason: 'cannot_reach' };
  await smoothLookAt(a.x + (-Math.sin(a.yaw)), a.y + 1.6, a.z + (-Math.cos(a.yaw)), 5);
  bot.swingArm('right');
  await new Promise(r => setTimeout(r, 300));
  return { ok: true, action_index: index, total_actions: playerActions.length };
}

async function interactWithBlock(blockName) {
  if (!bot.entity) return { ok: false, reason: 'no_bot' };
  const bp = bot.entity.position;
  let target = null, nd = Infinity;
  for (let x = -4; x <= 4; x++) {
    for (let y = -2; y <= 2; y++) {
      for (let z = -4; z <= 4; z++) {
        const p = bp.offset(x, y, z);
        const b = bot.blockAt(p);
        if (!b || b.name === 'air') continue;
        if (blockName && !b.name.includes(blockName)) continue;
        const d = Math.sqrt(x*x+y*y+z*z);
        if (d < nd && d > 0.5) { nd = d; target = b; }
      }
    }
  }
  if (!target) return { ok: false, reason: 'no_target', wanted: blockName };
  if (bp.distanceTo(target.position) > 2.5) {
    await goTo(target.position.x, target.position.z, 1.5, 5000);
  }
  await smoothLookAt(target.position.x + 0.5, target.position.y + 0.5, target.position.z + 0.5, 5);
  try {
    await bot.activateBlock(target);
    return { ok: true, interacted: target.name };
  } catch (e) {
    return { ok: false, reason: e.message };
  }
}

// ============ НОВЫЙ АЛГОРИТМ ВЫХОДА ИЗ ЯМЫ ============
async function escapePitRobust() {
  const startPos = bot.entity.position.clone();

  // ЭТАП 1: посмотреть вверх и прыгнуть если есть потолок
  for (let attempt = 0; attempt < 6; attempt++) {
    const bp = bot.entity.position;
    const up = bp.offset(0, 2, 0).floored();
    const blockUp = bot.blockAt(up);
    if (blockUp && blockUp.diggable) {
      try { await bot.dig(blockUp); } catch(e) {}
      bot.setControlState('jump', true);
      await new Promise(r => setTimeout(r, 500));
      bot.setControlState('jump', false);
      await new Promise(r => setTimeout(r, 200));
    }
    if (!isInPit()) return { ok: true, method: 'dig_up' };
  }

  // ЭТАП 2: круговой поиск выхода — прыгаем во все 8 направлений
  const dirs = [0, Math.PI/4, Math.PI/2, 3*Math.PI/4, Math.PI, 5*Math.PI/4, 3*Math.PI/2, 7*Math.PI/4];
  for (const angle of dirs) {
    const yaw = bot.entity.yaw + angle;
    bot.look(yaw, 0, false);
    await new Promise(r => setTimeout(r, 100));
    bot.setControlState('jump', true);
    bot.setControlState('forward', true);
    bot.setControlState('sprint', true);
    await new Promise(r => setTimeout(r, 700));
    bot.setControlState('jump', false);
    bot.setControlState('forward', false);
    bot.setControlState('sprint', false);
    await new Promise(r => setTimeout(r, 200));
    const dx = bot.entity.position.x - startPos.x;
    const dz = bot.entity.position.z - startPos.z;
    const dy = bot.entity.position.y - startPos.y;
    if (dx*dx + dz*dz > 4 || dy > 1) {
      return { ok: true, method: 'jump_' + Math.round(angle * 180 / Math.PI) };
    }
  }

  // ЭТАП 3: копаем вперёд на 3 блока во всех направлениях
  for (const angle of dirs) {
    const yaw = bot.entity.yaw + angle;
    bot.look(yaw, 0, false);
    await new Promise(r => setTimeout(r, 100));
    for (let i = 0; i < 3; i++) {
      const bp = bot.entity.position;
      const fp = bp.offset(-Math.sin(bot.entity.yaw), 0, -Math.cos(bot.entity.yaw)).floored();
      const block = bot.blockAt(fp);
      if (block && block.diggable) {
        try { await bot.dig(block); } catch(e) {}
      } else break;
    }
    bot.setControlState('forward', true);
    bot.setControlState('sprint', true);
    await new Promise(r => setTimeout(r, 800));
    bot.setControlState('forward', false);
    bot.setControlState('sprint', false);
    if (!isInPit()) return { ok: true, method: 'dig_tunnel' };
  }

  return { ok: false, method: 'failed', still_in_pit: isInPit() };
}

// === МОЩНЫЙ ВЫХОД ЧЕРЕЗ МНОГО ПОПЫТОК (для кризиса) ===
async function forceBreakOut() {
  console.log('🚨 FORCE BREAK OUT activated');
  for (let i = 0; i < 10; i++) {
    const yaw = Math.random() * Math.PI * 2;
    const pitch = (Math.random() - 0.5) * Math.PI;
    bot.look(yaw, pitch, false);
    await new Promise(r => setTimeout(r, 100));

    const bp = bot.entity.position;
    // Пробуем 4 блока в случайном направлении
    for (let j = 0; j < 4; j++) {
      const dx = -Math.sin(yaw) * Math.cos(pitch) * j;
      const dy = Math.sin(pitch) * j;
      const dz = -Math.cos(yaw) * Math.cos(pitch) * j;
      const probe = bp.offset(dx, dy, dz).floored();
      const b = bot.blockAt(probe);
      if (b && b.diggable) {
        try { await bot.dig(b); } catch(e) {}
      }
    }
    bot.setControlState('jump', true);
    bot.setControlState('forward', true);
    bot.setControlState('sprint', true);
    await new Promise(r => setTimeout(r, 600));
    bot.setControlState('jump', false);
    bot.setControlState('forward', false);
    bot.setControlState('sprint', false);
    await new Promise(r => setTimeout(r, 200));
  }
  return { ok: true, method: 'force_break_out_done' };
}

const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');

  if (req.url === '/state' && req.method === 'GET') {
    const pos = bot.entity ? bot.entity.position : { x:0, y:0, z:0 };
    const player = findNearestPlayer();
    let pi = null;
    if (player && player.entity) {
      const dx = player.entity.position.x - pos.x;
      const dz = player.entity.position.z - pos.z;
      pi = { name: player.username, x: player.entity.position.x,
        y: player.entity.position.y, z: player.entity.position.z,
        distance: Math.sqrt(dx*dx + dz*dz) };
    }
    const nearestHostile = findNearestHostile();
    res.end(JSON.stringify({
      x: pos.x, y: pos.y, z: pos.z,
      health: bot.health || 20, food: bot.food || 20,
      player: pi,
      in_pit: isInPit(),
      has_sky_above: hasSkyAbove(),
      is_night: bot.time.timeOfDay > 13000 && bot.time.timeOfDay < 23000,
      time_of_day: bot.time.timeOfDay,
      nearest_hostile: nearestHostile ? { name: nearestHostile.name, distance: nearestHostile.distance } : null,
      recent_damage: (Date.now() - lastDamageTime) < 2500,
      damage_time: lastDamageTime,
      bot_yaw: bot.entity ? bot.entity.yaw : 0,
      bot_pitch: bot.entity ? bot.entity.pitch : 0
    }));
    return;
  }

  if (req.url === '/self' && req.method === 'GET') {
    res.end(JSON.stringify({
      inventory: inventoryInfo(), armor: armorInfo(),
      health: bot.health, food: bot.food,
      pos: bot.entity ? { x: bot.entity.position.x, y: bot.entity.position.y, z: bot.entity.position.z } : null
    }));
    return;
  }

  if (req.url === '/vision' && req.method === 'GET') {
    res.end(JSON.stringify({
      visible_blocks: visibleBlocks(16),
      held_item: bot.heldItem ? bot.heldItem.name : null
    }));
    return;
  }

  if (req.url === '/sounds' && req.method === 'GET') {
    const now = Date.now();
    const recent = soundLog.filter(s => now - s.time < 5000);
    res.end(JSON.stringify({ sounds: recent }));
    return;
  }

  if (req.url === '/player_actions' && req.method === 'GET') {
    res.end(JSON.stringify({ actions: playerActions.slice(-20), total: playerActions.length }));
    return;
  }

  if (req.url === '/world' && req.method === 'GET') {
    res.end(JSON.stringify({
      blocks: nearbyBlocks(6),
      time: bot.time.timeOfDay,
      isDay: bot.time.timeOfDay < 13000
    }));
    return;
  }

  if (req.url === '/messages' && req.method === 'GET') {
    res.end(JSON.stringify({ messages: chatQueue })); return;
  }

  if (req.url === '/messages/clear' && req.method === 'POST') {
    chatQueue = []; res.end(JSON.stringify({ ok: true })); return;
  }

  if (req.url === '/actions' && req.method === 'GET') {
    res.end(JSON.stringify({ actions: ALL_ACTIONS })); return;
  }

  if (req.url === '/action' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const p = JSON.parse(body);
        const r = await handleAction(p.action, p.text, p.params);
        res.end(JSON.stringify({ ok: true, result: r }));
      } catch (e) {
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  res.end(JSON.stringify({ error: 'not found' }));
});

const ALL_ACTIONS = [
  { name: 'step_forward',  desc: 'шаг вперёд' },
  { name: 'step_back',     desc: 'шаг назад' },
  { name: 'step_left',     desc: 'шаг влево' },
  { name: 'step_right',    desc: 'шаг вправо' },
  { name: 'jump_once',     desc: 'прыжок на месте' },
  { name: 'jump_forward',  desc: 'прыжок вперёд' },
  { name: 'sprint_short',  desc: 'пробежка' },
  { name: 'sneak',         desc: 'присесть' },
  { name: 'go_to_player',  desc: 'идти к папе' },
  { name: 'walk_away_from_player', desc: 'отойти от папы' },
  { name: 'come_close_to_player',  desc: 'подойти вплотную' },
  { name: 'stay_here',     desc: 'стоять на месте' },
  { name: 'look_at_player',desc: 'посмотреть на папу' },
  { name: 'look_around',   desc: 'осмотреться' },
  { name: 'dig_forward',   desc: 'копать впереди' },
  { name: 'dig_down',      desc: 'копать под собой' },
  { name: 'dig_up',        desc: 'копать над собой' },
  { name: 'dig_nearby',    desc: 'копать ближайший блок' },
  { name: 'dig_tree',      desc: 'срубить дерево' },
  { name: 'escape_pit',    desc: 'выбраться из ямы' },
  { name: 'force_break_out', desc: 'аварийный выход (копать во все стороны)' },
  { name: 'place_block',   desc: 'поставить блок' },
  { name: 'build_shelter', desc: 'построить простое укрытие' },
  { name: 'drop_item',     desc: 'выбросить предмет' },
  { name: 'eat_food',      desc: 'съесть еду' },
  { name: 'equip_best_armor', desc: 'надеть броню' },
  { name: 'unequip_armor', desc: 'снять броню' },
  { name: 'hold_item',     desc: 'взять блок в руку' },
  { name: 'attack_nearest',desc: 'атаковать ближайшего моба' },
  { name: 'find_and_attack', desc: 'найти существо (params.target) и атаковать' },
  { name: 'flee_from_hostile', desc: 'убежать от враждебного моба' },
  { name: 'attack_hostile', desc: 'атаковать враждебного моба' },
  { name: 'look_up',       desc: 'посмотреть вверх' },
  { name: 'look_down',     desc: 'посмотреть вниз' },
  { name: 'spin_around',   desc: 'повернуться на 360' },
  { name: 'stop',          desc: 'остановиться' },
  { name: 'interact',      desc: 'нажать на блок (params.name)' },
  { name: 'wait_1sec',     desc: 'ждать 1 секунду' },
  { name: 'mimic_last',    desc: 'повторить последнее действие папы' },
  { name: 'look_at_position', desc: 'посмотреть в точку params.x,y,z' },
  { name: 'go_to_position', desc: 'идти к точке params.x, params.z' },
  { name: 'gather',        desc: 'добыть блок по названию (params.name или params.from)' },
  { name: 'craft',         desc: 'скрафтить предмет (params.name) на верстаке при нужде' },
  { name: 'place_table',   desc: 'поставить верстак рядом с собой' },
  { name: 'smelt',         desc: 'переплавить предмет в печи (params.name)' }
];

// --- КРАФТ И РЕМЕСЛО ---

function mcData() {
  try { return require('minecraft-data')(bot.version); }
  catch (e) { return null; }
}

// Добыть ближайший блок одного из имён (подстроки). Сам идёт к цели.
async function gatherBlock(names, maxDist = 16) {
  const bp = bot.entity.position;
  let best = null, bestD = 1e9;
  for (let x = -maxDist; x <= maxDist; x++) {
    for (let y = -4; y <= 4; y++) {
      for (let z = -maxDist; z <= maxDist; z++) {
        const pos = bp.offset(x, y, z);
        const b = bot.blockAt(pos);
        if (!b || !b.diggable) continue;
        if (names.some(n => b.name.includes(n))) {
          const d = Math.sqrt(x*x + y*y + z*z);
          if (d < bestD) { bestD = d; best = b; }
        }
      }
    }
  }
  if (!best) {
    // Не блок, а животное (шерсть со овцы): подойти и добыть.
    const animal = names.map(n => n.replace(/_wool$/, '')).find(a => PASSIVE.includes(a));
    if (animal) return await gatherFromAnimal(animal);
    return { ok: false, reason: 'not_found', wanted: names };
  }
  const dist = Math.hypot(best.position.x - bp.x, best.position.z - bp.z);
  if (dist > 3) {
    const ok = await goTo(best.position.x, best.position.z, 2, 8000);
    if (!ok) return { ok: false, reason: 'cannot_reach', wanted: names };
  }
  try {
    await smoothLookAt(best.position.x + 0.5, best.position.y + 0.5, best.position.z + 0.5, 3);
    const block = bot.blockAt(best.position);
    if (!block) return { ok: false, reason: 'block_gone' };
    await bot.dig(block);
    return { ok: true, gathered: block.name };
  } catch (e) { return { ok: false, reason: e.message }; }
}

// Добыть ресурс с животного (шерсть с овцы): подойти, бить, подобрать.
async function gatherFromAnimal(animalName) {
  const pos = bot.entity.position;
  let best = null, bestD = Infinity;
  for (const id in bot.entities) {
    const e = bot.entities[id];
    if (e === bot.entity || !e.position || !e.name) continue;
    if (e.name !== animalName) continue;
    const d = e.position.distanceTo(pos);
    if (d < bestD) { bestD = d; best = e; }
  }
  if (!best) return { ok: false, reason: 'animal_not_found', wanted: animalName };
  try {
    for (let hit = 0; hit < 8 && best.isValid; hit++) {
      if (bot.entity.position.distanceTo(best.position) > 3) {
        const ok = await goTo(best.position.x, best.position.z, 2, 5000);
        if (!ok) break;
      }
      await smoothLookAt(best.position.x, best.position.y + 0.8, best.position.z, 3);
      await bot.attack(best);
      await new Promise(r => setTimeout(r, 500));
    }
    await new Promise(r => setTimeout(r, 800));  // подобрать выпавший предмет
    return { ok: true, gathered: animalName };
  } catch (e) { return { ok: false, reason: e.message }; }
}

// Скрафтить предмет. Сначала пробуем в инвентаре, потом на верстаке.
async function craftItem(itemName, count = 1) {
  const mc = mcData();
  if (!mc) return { ok: false, reason: 'no_minecraft_data' };
  const item = mc.itemsByName[itemName];
  if (!item) return { ok: false, reason: 'unknown_item', item: itemName };

  let recipes = bot.recipesFor(item.id, null, 1, null);
  if (recipes && recipes.length) {
    try { await bot.craft(recipes[0], count, null); return { ok: true, crafted: itemName }; }
    catch (e) { return { ok: false, reason: e.message }; }
  }

  const tableBlock = mc.blocksByName['crafting_table'];
  const table = tableBlock
    ? bot.findBlock({ matching: tableBlock.id, maxDistance: 6 })
    : null;
  if (table) {
    recipes = bot.recipesFor(item.id, null, 1, table);
    if (recipes && recipes.length) {
      try {
        await smoothLookAt(table.position.x + 0.5, table.position.y + 0.5, table.position.z + 0.5, 3);
        await bot.craft(recipes[0], count, table);
        return { ok: true, crafted: itemName, at_table: true };
      } catch (e) { return { ok: false, reason: e.message }; }
    }
  }
  return { ok: false, reason: 'no_recipe_or_materials', item: itemName };
}

async function handleAction(action, text, params) {
  if (!bot.entity) return { ok: false, reason: 'bot_not_spawned' };
  const release = (keys, ms) => {
    setTimeout(() => keys.forEach(k => bot.setControlState(k, false)), ms);
  };

  switch (action) {
    case 'step_forward':  bot.setControlState('forward', true); release(['forward'], 500); return { ok: true };
    case 'step_back':     bot.setControlState('back', true); release(['back'], 500); return { ok: true };
    case 'step_left':     bot.setControlState('left', true); release(['left'], 500); return { ok: true };
    case 'step_right':    bot.setControlState('right', true); release(['right'], 500); return { ok: true };
    case 'jump_once':     bot.setControlState('jump', true); release(['jump'], 250); return { ok: true };
    case 'jump_forward':
      bot.setControlState('jump', true); bot.setControlState('forward', true);
      release(['jump','forward'], 600); return { ok: true };

    case 'sprint_short':
      if ((bot.food || 20) < 6) return { ok: false, reason: 'no_food_to_sprint' };
      bot.setControlState('sprint', true); bot.setControlState('forward', true);
      setTimeout(() => { bot.setControlState('sprint', false); bot.setControlState('forward', false); }, 2000);
      return { ok: true };

    case 'sneak':
      bot.setControlState('sneak', true); release(['sneak'], 1000); return { ok: true };

    case 'go_to_player': {
      const p = findNearestPlayer();
      if (!p || !p.entity) return { ok: false, reason: 'no_player' };
      const ok = await goTo(p.entity.position.x, p.entity.position.z, 2);
      return { ok, reason: ok ? 'arrived' : 'timeout' };
    }

    case 'come_close_to_player': {
      const p = findNearestPlayer();
      if (!p || !p.entity) return { ok: false, reason: 'no_player' };
      const ok = await goTo(p.entity.position.x, p.entity.position.z, 1);
      return { ok, reason: ok ? 'arrived' : 'timeout' };
    }

    case 'walk_away_from_player': {
      const p = findNearestPlayer();
      if (!p || !p.entity) return { ok: false, reason: 'no_player' };
      const bp = bot.entity.position, pp = p.entity.position;
      const dx = bp.x - pp.x, dz = bp.z - pp.z;
      const len = Math.sqrt(dx*dx + dz*dz) || 1;
      const ok = await goTo(bp.x + (dx/len)*15, bp.z + (dz/len)*15, 2, 5000);
      return { ok, reason: ok ? 'moved_away' : 'timeout' };
    }

    case 'stay_here':
      ['forward','back','left','right','jump','sprint','sneak'].forEach(k => bot.setControlState(k, false));
      await new Promise(r => setTimeout(r, 2000));
      return { ok: true };

    case 'look_at_player': {
      const p = findNearestPlayer();
      if (!p || !p.entity) return { ok: false, reason: 'no_player' };
      const pp = p.entity.position;
      await smoothLookAt(pp.x, pp.y + 1.6, pp.z, 5);
      return { ok: true };
    }

    case 'look_around':
      (async () => {
        for (let i = 0; i < 4; i++) {
          bot.look(bot.entity.yaw + Math.PI / 2, 0, false);
          await new Promise(r => setTimeout(r, 300));
        }
      })(); return { ok: true };

    case 'dig_forward': {
      const bp = bot.entity.position;
      const fp = bp.offset(-Math.sin(bot.entity.yaw), 0, -Math.cos(bot.entity.yaw)).floored();
      const block = bot.blockAt(fp);
      if (!block || !block.diggable) return { ok: false, reason: 'nothing_to_dig' };
      try { await bot.dig(block); return { ok: true, dug: block.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'dig_down': {
      const bp = bot.entity.position;
      const dp = bp.offset(0, -1, 0).floored();
      const block = bot.blockAt(dp);
      if (!block || !block.diggable) return { ok: false, reason: 'nothing_to_dig' };
      try { await bot.dig(block); return { ok: true, dug: block.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'dig_up': {
      const bp = bot.entity.position;
      const up = bp.offset(0, 2, 0).floored();
      const block = bot.blockAt(up);
      if (!block || !block.diggable) return { ok: false, reason: 'nothing_to_dig' };
      try { await bot.dig(block); return { ok: true, dug: block.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'dig_nearby': {
      const feet = bot.entity.position.floored();
      // Никогда не копаем блок под собственными ногами — иначе падаем
      // в яму, которую сами же вырыли.
      const blocks = nearbyBlocks(4).filter(b => b.diggable &&
        !(b.x === feet.x && b.z === feet.z && b.y === feet.y - 1));
      if (blocks.length === 0) return { ok: false, reason: 'no_diggable_block' };
      const target = blocks[0];
      try {
        await smoothLookAt(target.x + 0.5, target.y + 0.5, target.z + 0.5, 3);
        const block = bot.blockAt(vec3(target.x, target.y, target.z));
        if (!block) return { ok: false, reason: 'block_gone' };
        await bot.dig(block);
        return { ok: true, dug: target.name };
      } catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'dig_tree': {
      const bp = bot.entity.position;
      let logs = [];
      for (let x = -16; x <= 16; x++) {
        for (let y = -3; y <= 8; y++) {
          for (let z = -16; z <= 16; z++) {
            const pos = bp.offset(x, y, z);
            const b = bot.blockAt(pos);
            if (b && (b.name.includes('log') || b.name.includes('wood'))) {
              logs.push({ name: b.name, pos: pos, dist: Math.sqrt(x*x+y*y+z*z) });
            }
          }
        }
      }
      if (logs.length === 0) return { ok: false, reason: 'no_tree_nearby' };
      logs.sort((a,b) => a.dist - b.dist);
      const target = logs[0];
      const dist = Math.sqrt((target.pos.x-bp.x)**2 + (target.pos.z-bp.z)**2);
      if (dist > 2.5) {
        const ok = await goTo(target.pos.x, target.pos.z, 2, 8000);
        if (!ok) return { ok: false, reason: 'cannot_reach_tree' };
      }
      let dug = 0;
      for (let i = 0; i < 5; i++) {
        const up = logs.find(l => l.name === target.name &&
          Math.abs(l.pos.x - target.pos.x) < 1 && Math.abs(l.pos.z - target.pos.z) < 1 &&
          l.pos.y >= target.pos.y + i);
        if (!up) break;
        const block = bot.blockAt(vec3(up.pos.x, up.pos.y, up.pos.z));
        if (!block) continue;
        try {
          await smoothLookAt(up.pos.x + 0.5, up.pos.y + 0.5, up.pos.z + 0.5, 3);
          await bot.dig(block);
          dug++;
        } catch(e) { break; }
      }
      return { ok: dug > 0, dug_blocks: dug };
    }

    case 'escape_pit':
      return await escapePitRobust();

    case 'force_break_out':
      return await forceBreakOut();

    case 'place_block': {
      const item = bot.heldItem;
      if (!item) return { ok: false, reason: 'no_block_in_hand' };
      const isBlock = ['block','plank','dirt','stone','cobble','log','wood','sand','gravel']
        .some(s => item.name.includes(s));
      if (!isBlock) return { ok: false, reason: 'held_item_not_block', held: item.name };
      const bp = bot.entity.position;
      const dx = -Math.sin(bot.entity.yaw), dz = -Math.cos(bot.entity.yaw);
      const belowFront = bp.offset(dx, -1, dz).floored();
      const ref = bot.blockAt(belowFront);
      if (!ref || ref.boundingBox !== 'block') return { ok: false, reason: 'no_surface_to_place_on' };
      try { await bot.placeBlock(ref, vec3(0, 1, 0)); return { ok: true, placed: item.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'build_shelter': {
      let placed = 0;
      const directions = [[1,0],[0,1],[-1,0],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]];
      const bp = bot.entity.position;
      for (const [dx, dz] of directions) {
        const target = bp.offset(dx, 0, dz).floored();
        const below = bot.blockAt(target.offset(0, -1, 0));
        if (!below || below.boundingBox !== 'block') continue;
        const existing = bot.blockAt(target);
        if (existing && existing.boundingBox === 'block') continue;
        const item = bot.heldItem;
        if (!item) break;
        try {
          await smoothLookAt(target.x + 0.5, target.y + 0.5, target.z + 0.5, 3);
          await bot.placeBlock(below, vec3(0, 1, 0));
          placed++;
        } catch(e) { break; }
        if (placed >= 4) break;
      }
      return { ok: placed > 0, placed };
    }

    case 'drop_item': {
      const items = bot.inventory.items();
      if (items.length === 0) return { ok: false, reason: 'empty_inventory' };
      try { await bot.tossStack(items[0]); return { ok: true, dropped: items[0].name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'eat_food': {
      const food = bot.inventory.items().find(i =>
        ['bread','apple','beef','pork','chicken','carrot','potato','cooked']
          .some(s => i.name.includes(s)));
      if (!food) return { ok: false, reason: 'no_food' };
      if ((bot.food || 20) >= 20) return { ok: false, reason: 'food_is_full' };
      try { await bot.equip(food, 'hand'); await bot.consume(); return { ok: true, ate: food.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'equip_best_armor': {
      const ranks = { netherite: 4, diamond: 3, iron: 2, chainmail: 1.5, golden: 1, leather: 0.5 };
      const slots = { helmet: 'head', chestplate: 'torso', leggings: 'legs', boots: 'feet' };
      const equipped = [];
      const items = bot.inventory.items();
      for (const suf in slots) {
        const candidates = items.filter(i => i.name.endsWith(suf));
        if (candidates.length === 0) continue;
        let best = candidates[0], bestRank = -1;
        for (const c of candidates) {
          const r = ranks[c.name.split('_')[0]] || 0;
          if (r > bestRank) { bestRank = r; best = c; }
        }
        try { await bot.equip(best, slots[suf]); equipped.push(best.name); } catch (e) {}
      }
      return { ok: equipped.length > 0, equipped };
    }

    case 'unequip_armor': {
      const removed = [];
      for (const s of ['head', 'torso', 'legs', 'feet']) {
        try { await bot.unequip(s); removed.push(s); } catch (e) {}
      }
      return { ok: true, removed };
    }

    case 'gather': {
      const names = (params && (params.from || params.name))
        ? (Array.isArray(params.from || params.name) ? (params.from || params.name) : [params.name])
        : ['log', 'stone', 'coal_ore', 'iron_ore'];
      return await gatherBlock(names);
    }

    case 'craft':
      if (!params || !params.name) return { ok: false, reason: 'no_item_name' };
      return await craftItem(params.name, (params && params.count) || 1);

    case 'place_table': {
      const mc = mcData();
      const table = bot.inventory.items().find(i => i.name === 'crafting_table');
      if (!table) return { ok: false, reason: 'no_crafting_table' };
      try {
        await bot.equip(table, 'hand');
        const bp = bot.entity.position;
        const dx = -Math.sin(bot.entity.yaw), dz = -Math.cos(bot.entity.yaw);
        const ref = bot.blockAt(bp.offset(dx, -1, dz).floored());
        if (!ref || ref.boundingBox !== 'block') return { ok: false, reason: 'no_surface' };
        await bot.placeBlock(ref, vec3(0, 1, 0));
        return { ok: true, placed: 'crafting_table' };
      } catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'smelt': {
      const mc = mcData();
      const itemName = (params && params.name) || 'raw_iron';
      const input = bot.inventory.items().find(i => i.name === itemName);
      if (!input) return { ok: false, reason: 'no_input', wanted: itemName };
      const fuel = bot.inventory.items().find(i =>
        ['coal', 'oak_planks', 'birch_planks', 'log', 'charcoal'].some(s => i.name.includes(s)));
      if (!fuel) return { ok: false, reason: 'no_fuel' };
      const furnaceBlock = mc && mc.blocksByName['furnace'];
      let furnace = furnaceBlock
        ? bot.findBlock({ matching: furnaceBlock.id, maxDistance: 6 })
        : null;
      if (!furnace) {
        const furnaceItem = bot.inventory.items().find(i => i.name === 'furnace');
        if (!furnaceItem) return { ok: false, reason: 'no_furnace' };
        try {
          await bot.equip(furnaceItem, 'hand');
          const bp = bot.entity.position;
          const dx = -Math.sin(bot.entity.yaw), dz = -Math.cos(bot.entity.yaw);
          const ref = bot.blockAt(bp.offset(dx, -1, dz).floored());
          if (ref && ref.boundingBox === 'block') {
            await bot.placeBlock(ref, vec3(0, 1, 0));
            furnace = bot.findBlock({ matching: furnaceBlock.id, maxDistance: 6 });
          }
        } catch (e) {}
      }
      if (!furnace) return { ok: false, reason: 'cannot_place_furnace' };
      try {
        await smoothLookAt(furnace.position.x + 0.5, furnace.position.y + 0.5, furnace.position.z + 0.5, 3);
        await bot.openFurnace(furnace);
        await bot.putInput(input);
        await bot.putFuel(fuel);
        await new Promise(r => setTimeout(r, 1200));
        await bot.closeWindow(bot.currentWindow);
        return { ok: true, smelted: itemName };
      } catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'hold_item': {
      let item = null;
      if (params && params.name) {
        item = bot.inventory.items().find(i => i.name.includes(params.name));
        if (!item) return { ok: false, reason: 'item_not_found', wanted: params.name };
      } else {
        item = bot.inventory.items().find(i =>
          ['block','plank','dirt','stone','cobble','log','wood','sand','gravel']
            .some(s => i.name.includes(s)));
        if (!item) return { ok: false, reason: 'no_block_in_inventory' };
      }
      try { await bot.equip(item, 'hand'); return { ok: true, holding: item.name }; }
      catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'attack_nearest': {
      const target = findNearestPassive();
      if (!target) return { ok: false, reason: 'no_target' };
      try {
        await smoothLookAt(target.position.x, target.position.y + 1.6, target.position.z, 3);
        await bot.attack(target);
        return { ok: true, attacked: target.name };
      } catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'find_and_attack': {
      const keyword = (params && params.target) ? params.target : 'pig';
      let target = null;
      const pos = bot.entity.position;
      let nd = Infinity;
      for (const id in bot.entities) {
        const e = bot.entities[id];
        if (!e.name || !e.position || e === bot.entity) continue;
        if (!e.name.includes(keyword)) continue;
        const d = e.position.distanceTo(pos);
        if (d < nd) { nd = d; target = e; }
      }
      if (!target) return { ok: false, reason: 'target_not_found' };
      if (bot.entity.position.distanceTo(target.position) > 3) {
        const ok = await goTo(target.position.x, target.position.z, 2.5, 6000);
        if (!ok) return { ok: false, reason: 'cannot_reach_target' };
      }
      try {
        await smoothLookAt(target.position.x, target.position.y + 1.6, target.position.z, 3);
        await bot.attack(target);
        return { ok: true, attacked: target.name };
      } catch (e) { return { ok: false, reason: e.message }; }
    }

    case 'flee_from_hostile': {
      const hostile = findNearestHostile();
      if (!hostile) return { ok: false, reason: 'no_hostile' };
      const bp = bot.entity.position;
      const dx = bp.x - hostile.x, dz = bp.z - hostile.z;
      const len = Math.sqrt(dx*dx + dz*dz) || 1;
      const ok = await goTo(bp.x + (dx/len) * 20, bp.z + (dz/len) * 20, 2, 6000);
      return { ok, reason: ok ? 'escaped' : 'timeout' };
    }

    case 'attack_hostile': {
      const hostile = findNearestHostile();
      if (!hostile) return { ok: false, reason: 'no_hostile' };
      if (hostile.name === 'creeper') return { ok: false, reason: 'creeper_dangerous' };
      const e = hostile.entity;
      if (bot.entity.position.distanceTo(e.position) > 3) {
        const ok = await goTo(e.position.x, e.position.z, 2.5, 5000);
        if (!ok) return { ok: false, reason: 'cannot_reach' };
      }
      try {
        await smoothLookAt(e.position.x, e.position.y + 1.6, e.position.z, 3);
        await bot.attack(e);
        return { ok: true, attacked: hostile.name };
      } catch (err) { return { ok: false, reason: err.message }; }
    }

    case 'look_up': bot.look(bot.entity.yaw, -Math.PI/2, false); return { ok: true };
    case 'look_down': bot.look(bot.entity.yaw, Math.PI/2, false); return { ok: true };
    case 'spin_around':
      (async () => {
        for (let i = 0; i < 8; i++) {
          bot.look(bot.entity.yaw + Math.PI / 4, 0, false);
          await new Promise(r => setTimeout(r, 200));
        }
      })(); return { ok: true };

    case 'stop':
      ['forward','back','left','right','jump','sprint','sneak'].forEach(k => bot.setControlState(k, false));
      return { ok: true };

    case 'interact': {
      const blockName = params && params.name ? params.name : null;
      return await interactWithBlock(blockName);
    }

    case 'wait_1sec':
      await new Promise(r => setTimeout(r, 1000));
      return { ok: true };

    case 'mimic_last': {
      if (playerActions.length === 0) return { ok: false, reason: 'no_actions_recorded' };
      const idx = (params && params.index !== undefined) ? params.index : -1;
      return await mimicPlayerAction(idx);
    }

    case 'look_at_position': {
      if (!params || params.x === undefined) return { ok: false, reason: 'no_position' };
      await smoothLookAt(params.x, params.y || bot.entity.position.y + 1, params.z, 6);
      return { ok: true };
    }

    case 'go_to_position': {
      if (!params || params.x === undefined) return { ok: false, reason: 'no_position' };
      const ok = await goTo(params.x, params.z, 1.5, 8000);
      return { ok, reason: ok ? 'arrived' : 'timeout' };
    }

    case 'say':
      if (text && typeof text === 'string') bot.chat(String(text).slice(0, 200));
      return { ok: true };

    default:
      return { ok: false, reason: 'unknown_action' };
  }
}

server.listen(3000, () => {
  console.log('=================================');
  console.log('HTTP на 3000 | Действий: ' + ALL_ACTIONS.length);
  console.log('=================================');
});

bot.on('end', () => { console.log('Отключён'); server.close(); });