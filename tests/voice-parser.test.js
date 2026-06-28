const assert = require('assert');
const { parseVoiceNote } = require('../app/static/voice-parser.js');

const config = {
  projectNames: ['Jura', 'Meta Street'],
  buildings: ['B1', 'B2', 'B3', 'B4', 'Building 1', 'Building 2', 'Building 3', 'Building 4'],
  levels: ['Ground', 'Level 1', 'Level 2', 'Level 3', 'Roof'],
  units: ['U101', 'U204', 'U207', 'U305', 'Unit 305'],
  rooms: ['Balcony', 'Ensuite', 'Bathroom', 'Roof', 'External', 'Entry', 'Kitchen', 'Corridor'],
  trades: ['Tiling', 'Painting', 'Plastering', 'Waterproofing', 'Joinery', 'Render'],
  subcontractors: [],
};

function has(value, allowed) {
  assert(allowed.includes(value), `expected ${value} to be one of ${allowed.join(', ')}`);
}

function test(name, input, checks) {
  const parsed = parseVoiceNote(input, config);
  checks(parsed);
  console.log(`✓ ${name}`);
}

test('building/unit/balcony/level tiling example cleans description',
  'Building 3, Unit 305, Balcony, on Level 1, tiling to be repaired.',
  (p) => {
    has(p.building, ['B3', 'Building 3']);
    has(p.unit, ['U305', 'Unit 305']);
    assert.strictEqual(p.room, 'Balcony');
    assert.strictEqual(p.level, 'Level 1');
    assert.strictEqual(p.trade, 'Tiling');
    assert.strictEqual(p.description, 'Tiling to be repaired.');
    assert.notStrictEqual(p.description, p.raw_transcript);
  });

test('ensuite cracked tile replacement',
  'B2 level 2 unit 204 ensuite cracked tile under vanity, tiler to replace and regrout.',
  (p) => {
    assert.strictEqual(p.building, 'B2');
    assert.strictEqual(p.level, 'Level 2');
    assert.strictEqual(p.unit, 'U204');
    assert.strictEqual(p.room, 'Ensuite');
    assert.strictEqual(p.trade, 'Tiling');
    assert.strictEqual(p.description, 'Cracked tile under vanity. Tiler to replace and regrout.');
  });

test('bathroom paint defect',
  'Building 4 unit 101 bathroom paint defect, painter to patch and repaint wall.',
  (p) => {
    has(p.building, ['B4', 'Building 4']);
    assert.strictEqual(p.unit, 'U101');
    assert.strictEqual(p.room, 'Bathroom');
    assert.strictEqual(p.trade, 'Painting');
    assert.strictEqual(p.description, 'Paint defect. Painter to patch and repaint wall.');
  });

test('meta roof waterproofing incomplete work',
  'Meta Street roof incomplete silicone around penetration waterproofer to review.',
  (p) => {
    assert.strictEqual(p.project, 'Meta Street');
    assert.strictEqual(p.room, 'Roof');
    assert.strictEqual(p.trade, 'Waterproofing');
    assert.strictEqual(p.description, 'Incomplete silicone around penetration. Waterproofer to review.');
  });

test('ground external render damage',
  'B1 ground floor external render damage near entry, renderer to make good.',
  (p) => {
    assert.strictEqual(p.building, 'B1');
    assert.strictEqual(p.level, 'Ground');
    has(p.room, ['External', 'Entry']);
    assert.strictEqual(p.trade, 'Render');
    assert.strictEqual(p.description, 'Render damage near entry. Renderer to make good.');
  });

test('kitchen joinery scratched door',
  'Unit 207 kitchen joinery door scratched, cabinet maker to replace.',
  (p) => {
    assert.strictEqual(p.unit, 'U207');
    assert.strictEqual(p.room, 'Kitchen');
    assert.strictEqual(p.trade, 'Joinery');
    assert.strictEqual(p.description, 'Joinery door scratched. Cabinet maker to replace.');
  });

test('corridor plasterboard crack',
  'Level three corridor plasterboard crack, plasterer to patch sand and paint ready.',
  (p) => {
    assert.strictEqual(p.level, 'Level 3');
    assert.strictEqual(p.room, 'Corridor');
    assert.strictEqual(p.trade, 'Plastering');
    assert.strictEqual(p.description, 'Plasterboard crack. Plasterer to patch, sand and paint ready.');
  });
