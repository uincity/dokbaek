// Exercise the actual date/selection helpers without loading the page DOM.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/js/site.js', 'utf8');
const helpers = source.slice(source.indexOf('function seoulToday('), source.indexOf('function repertoireTable('));
const order = source.slice(source.indexOf('function ordered('), source.indexOf('function occurrences('));
const context = vm.createContext({Intl, Date});
vm.runInContext(order + helpers, context);
assert.equal(context.seoulToday(new Date('2026-10-14T14:59:59Z')), '2026-10-14');
assert.equal(context.seoulToday(new Date('2026-10-14T15:00:00Z')), '2026-10-15');
const concert = (id, date, extra={}) => ({id,date,datePrecision:'day',visibility:'public',status:'scheduled',...extra});
const rows = [concert('later','2026-11-01'),concert('today','2026-10-15'),
  concert('past','2026-10-14'),concert('month','2026-10',{datePrecision:'month'}),
  concert('unknown',null,{datePrecision:'unknown'}),concert('private','2026-10-16',{visibility:'private'}),
  concert('done','2026-10-16',{status:'completed'}),concert('summary','2026-10-16',{visibility:'public-summary',mediaVisibility:'withheld'})];
const before = JSON.stringify(rows);
const result = context.homeSchedule(rows,'2026-10-15');
assert.equal(result.upcoming.map(c=>c.id).join(','),'today,summary,later');
assert.equal(result.past.map(c=>c.id).join(','),'past');
assert.equal(result.pending.map(c=>c.id).join(','),'unknown,month');
assert.equal(JSON.stringify(rows),before);
assert.equal(context.homeSchedule([], '2026-10-15').upcoming.length,0);
assert.equal(context.homeSchedule(rows, '2027-01-01').upcoming.length,0);
console.log('PASS: Seoul midnight, today, sorted future dates, past scheduled, month/unknown, privacy, completed, empty and immutable data');
