// Static definitions: enemies, relics, tuning constants.

export const PLAYER_BASE = {
  hp: 6,
  dmg: 2,
  shards: 1, // rewind charges per loop
  attempts: 6, // loops per floor
  echoes: 3, // max echoes alive
  echoDmg: 2,
  potionHeal: 3,
  lantern: 8, // base sight radius
  gateOpenTurns: 6, // how long a plate keeps the gate open
};

export const ENEMY_DEFS = {
  husk: { name: 'Husk', hp: 3, dmg: 1, sight: 7, glyph: 'H' },
  sniper: { name: 'Sniper', hp: 2, dmg: 1, sight: 8, glyph: 'S' },
  charger: { name: 'Charger', hp: 4, dmg: 2, sight: 7, glyph: 'C' },
  warden: { name: 'Warden', hp: 12, dmg: 2, sight: 9, glyph: 'W', boss: true },
};

export const RELICS = [
  { id: 'second_echo', name: 'Second Echo', desc: 'Лимит эхо +1.' },
  { id: 'iron_heart', name: 'Iron Heart', desc: 'Макс. HP +2 и сразу +2 HP.' },
  { id: 'lantern', name: 'Lantern', desc: 'Радиус обзора +2.' },
  { id: 'echo_edge', name: 'Echo Edge', desc: 'Эхо бьют на +1 урона.' },
  { id: 'second_chance', name: 'Second Chance', desc: 'Осколков отмотки +1 за петлю.' },
  { id: 'sharp_steel', name: 'Sharp Steel', desc: 'Твой урон +1.' },
  { id: 'extra_loop', name: 'Extra Loop', desc: 'Попыток (петель) на этаж +1.' },
];

export const FLOOR_COUNT = 5;

/** Derive effective stats from owned relics. Pure. */
export function modsOf(relics) {
  const has = (id) => relics.includes(id);
  const count = (id) => relics.filter((r) => r === id).length;
  return {
    maxHp: PLAYER_BASE.hp + 2 * count('iron_heart'),
    playerDmg: PLAYER_BASE.dmg + count('sharp_steel'),
    echoDmg: PLAYER_BASE.echoDmg + count('echo_edge'),
    maxEchoes: PLAYER_BASE.echoes + count('second_echo'),
    lantern: PLAYER_BASE.lantern + (has('lantern') ? 2 : 0),
    shards: PLAYER_BASE.shards + count('second_chance'),
    attempts: PLAYER_BASE.attempts + count('extra_loop'),
  };
}
