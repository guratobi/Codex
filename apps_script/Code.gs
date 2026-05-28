/**
 * 내일 날씨 / 미세먼지 / 강수·우산 알림 — Google Apps Script 버전.
 *
 * GitHub Actions 대신 구글 서버에서 매일 정해진 시각에 실행된다 (PC 꺼져도 작동).
 *
 * === 설정 방법 ===
 * 1) https://script.google.com 접속 → "새 프로젝트"
 * 2) 이 파일 내용 전체를 붙여넣기
 * 3) 좌측 톱니바퀴(프로젝트 설정) → "스크립트 속성"에 아래 값 추가:
 *      OWM_API_KEY        = (OpenWeatherMap 키)
 *      TELEGRAM_TOKEN     = (텔레그램 봇 토큰)
 *      TELEGRAM_CHAT_ID   = (chat id)
 *    선택:
 *      HOME_LAT (기본 37.6018) / HOME_LON (기본 127.0537) / HOME_LABEL (기본 이문동)
 *      QUIET_MODE (기본 true)  / TOMORROW_API_KEY (꽃가루, 있을 때만)
 * 4) 함수 목록에서 testSend 선택 후 실행 → 텔레그램에 즉시 테스트 메시지 도착 확인
 *    (첫 실행 시 권한 승인 팝업이 뜨면 허용)
 * 5) 함수 목록에서 setupTrigger 실행 → 매일 21:00(KST) 자동 실행 트리거 설치
 */

var KST_MS = 9 * 3600 * 1000;
var PM25_BREAKS = [[15, '좋음'], [35, '보통'], [75, '나쁨'], [1e9, '매우나쁨']];
var POLLEN_LABELS = ['없음', '매우낮음', '낮음', '보통', '높음', '매우높음'];
var WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

function prop(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return (v === null || v === '') ? fallback : v;
}

function fetchJson(url) {
  var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var code = resp.getResponseCode();
  if (code >= 300) {
    throw new Error('HTTP ' + code + ' — ' + resp.getContentText().slice(0, 200));
  }
  return JSON.parse(resp.getContentText());
}

function tomorrowWindow() {
  var k = new Date(Date.now() + KST_MS);
  var y = k.getUTCFullYear(), m = k.getUTCMonth(), d = k.getUTCDate();
  var startMs = Date.UTC(y, m, d + 1, 0, 0, 0) - KST_MS;
  return { startSec: startMs / 1000, endSec: startMs / 1000 + 86400, startMs: startMs };
}

function kstHour(dtSec) {
  return new Date(dtSec * 1000 + KST_MS).getUTCHours();
}

function grade(value, breaks) {
  for (var i = 0; i < breaks.length; i++) {
    if (value <= breaks[i][0]) return breaks[i][1];
  }
  return '알수없음';
}

// ---- 데이터 가져오기 ----
function fetchForecast(lat, lon, key) {
  var u = 'https://api.openweathermap.org/data/2.5/forecast?lat=' + lat + '&lon=' + lon +
    '&appid=' + key + '&units=metric&lang=kr';
  return fetchJson(u);
}

function fetchAir(lat, lon, key) {
  var u = 'https://api.openweathermap.org/data/2.5/air_pollution/forecast?lat=' + lat +
    '&lon=' + lon + '&appid=' + key;
  return fetchJson(u);
}

function fetchPollen(lat, lon, key) {
  if (!key) return null;
  try {
    var u = 'https://api.tomorrow.io/v4/timelines?location=' + lat + ',' + lon +
      '&fields=treeIndex,grassIndex,weedIndex&timesteps=1d&timezone=Asia/Seoul&apikey=' + key;
    return fetchJson(u);
  } catch (e) {
    Logger.log('pollen fetch failed: ' + e);
    return null;
  }
}

function filterTomorrow(list) {
  var w = tomorrowWindow();
  return (list || []).filter(function (it) {
    return it.dt >= w.startSec && it.dt < w.endSec;
  });
}

// ---- 요약 ----
var BUCKETS = [[0, 6, '새벽'], [6, 12, '오전'], [12, 18, '오후'], [18, 24, '저녁']];

function bucketFor(h) {
  for (var i = 0; i < BUCKETS.length; i++) {
    if (h >= BUCKETS[i][0] && h < BUCKETS[i][1]) return BUCKETS[i][2];
  }
  return '저녁';
}

function timeOfDayFlow(slots) {
  var order = [], buckets = {};
  slots.forEach(function (s) {
    var name = bucketFor(kstHour(s.dt));
    if (!buckets[name]) { buckets[name] = {}; order.push(name); }
    var desc = s.weather[0].description;
    buckets[name][desc] = (buckets[name][desc] || 0) + 1;
  });
  var seq = order.map(function (n) {
    var counts = buckets[n], best = null, bestC = -1;
    for (var d in counts) { if (counts[d] > bestC) { bestC = counts[d]; best = d; } }
    return [n, best];
  });
  var merged = [];
  seq.forEach(function (pair) {
    if (merged.length && merged[merged.length - 1][1] === pair[1]) {
      merged[merged.length - 1][0].push(pair[0]);
    } else {
      merged.push([[pair[0]], pair[1]]);
    }
  });
  if (merged.length === 1) {
    return merged[0][0].length === order.length ? merged[0][1]
      : merged[0][0].join('·') + ' ' + merged[0][1];
  }
  return merged.map(function (m) { return m[0].join('·') + ' ' + m[1]; }).join(' → ');
}

function rainText(totalMm, slotCount) {
  if (totalMm < 1) return '약한 비';
  if (slotCount <= 1 && totalMm / slotCount >= 4) return '소나기';
  if (totalMm < 5) return '약한 비';
  if (totalMm < 15) return '보통 비';
  if (totalMm < 30) return '강한 비';
  return '매우 강한 비';
}

function summarizeWeather(slots) {
  var feels = slots.map(function (s) { return s.main.feels_like; });
  var rainSlots = [];
  slots.forEach(function (s) {
    var rain = (s.rain && s.rain['3h']) || 0;
    var snow = (s.snow && s.snow['3h']) || 0;
    var pop = s.pop || 0;
    if (rain > 0 || snow > 0 || pop >= 0.5) {
      rainSlots.push({ dt: s.dt, rain: rain, snow: snow });
    }
  });
  return {
    feelsMin: feels.length ? Math.min.apply(null, feels) : null,
    feelsMax: feels.length ? Math.max.apply(null, feels) : null,
    flow: slots.length ? timeOfDayFlow(slots) : '정보없음',
    rainSlots: rainSlots,
    maxPop: slots.reduce(function (a, s) { return Math.max(a, s.pop || 0); }, 0)
  };
}

function summarizeAir(slots) {
  if (!slots.length) return null;
  var pm25 = slots.reduce(function (a, s) { return Math.max(a, s.components.pm2_5); }, 0);
  return { pm25Max: pm25, grade: grade(pm25, PM25_BREAKS) };
}

function summarizePollen(payload) {
  if (!payload) return null;
  var w = tomorrowWindow();
  var intervals = (((payload.data || {}).timelines || [{}])[0] || {}).intervals || [];
  for (var i = 0; i < intervals.length; i++) {
    var t = new Date(intervals[i].startTime).getTime() / 1000;
    if (t >= w.startSec && t < w.endSec) {
      var v = intervals[i].values || {};
      return { tree: v.treeIndex || 0, grass: v.grassIndex || 0, weed: v.weedIndex || 0 };
    }
  }
  return null;
}

// ---- 메시지 줄 ----
function umbrellaLine(w) {
  if (!w.rainSlots.length) return null;
  var first = kstHour(w.rainSlots[0].dt);
  var last = kstHour(w.rainSlots[w.rainSlots.length - 1].dt) + 3;
  var totalRain = w.rainSlots.reduce(function (a, s) { return a + s.rain; }, 0);
  var totalSnow = w.rainSlots.reduce(function (a, s) { return a + s.snow; }, 0);
  var when = ('0' + first).slice(-2) + '~' + ('0' + last).slice(-2) + '시';
  if (totalSnow) return '☔ ' + when + ' 눈';
  return '☔ ' + when + ' ' + rainText(totalRain, w.rainSlots.length);
}

function airLine(air) {
  if (!air || air.grade === '좋음' || air.grade === '보통') return null;
  return '😷 미세먼지 ' + air.grade + ' (' + Math.round(air.pm25Max) + ')';
}

function pollenLine(p) {
  if (!p) return null;
  var items = [['나무', p.tree], ['잔디', p.grass], ['잡초', p.weed]];
  var peak = items[0];
  items.forEach(function (it) { if (it[1] > peak[1]) peak = it; });
  if (peak[1] < 4) return null;
  return '🌳 ' + peak[0] + ' 꽃가루 ' + POLLEN_LABELS[peak[1]];
}

function diffLine(todayMax, tomorrowMax) {
  if (todayMax === null || todayMax === undefined) return null;
  var delta = tomorrowMax - todayMax;
  if (Math.abs(delta) < 5) return null;
  return delta > 0 ? '📈 오늘보다 ' + Math.round(delta) + '°C 따뜻'
    : '📉 오늘보다 ' + Math.round(Math.abs(delta)) + '°C 추움';
}

function isRoutineDay(w, air, pollen, todayMax) {
  if (w.rainSlots.length || w.maxPop >= 0.3) return false;
  if (air && air.grade !== '좋음' && air.grade !== '보통') return false;
  if (pollen && Math.max(pollen.tree, pollen.grass, pollen.weed) >= 4) return false;
  if (todayMax !== null && todayMax !== undefined && w.feelsMax !== null &&
    Math.abs(w.feelsMax - todayMax) >= 5) return false;
  return true;
}

function buildMessage(w, air, pollen, label, todayMax) {
  var t = tomorrowWindow();
  var k = new Date(t.startMs + KST_MS);
  var dateStr = (k.getUTCMonth() + 1) + '/' + k.getUTCDate() + ' (' + WEEKDAYS[k.getUTCDay()] + ')';
  var lines = ['🗓 *' + dateStr + '* ' + label];
  var feels = (w.feelsMin !== null) ?
    '체감 ' + Math.round(w.feelsMin) + '~' + Math.round(w.feelsMax) + '°C' : '';
  lines.push(('☁️ ' + w.flow + (feels ? ', ' + feels : '')));
  [umbrellaLine(w), airLine(air), pollenLine(pollen),
    (w.feelsMax !== null ? diffLine(todayMax, w.feelsMax) : null)
  ].forEach(function (l) { if (l) lines.push(l); });
  return lines.join('\n');
}

function sendTelegram(text) {
  var token = prop('TELEGRAM_TOKEN');
  var chat = prop('TELEGRAM_CHAT_ID');
  var url = 'https://api.telegram.org/bot' + token + '/sendMessage';
  var resp = UrlFetchApp.fetch(url, {
    method: 'post',
    payload: { chat_id: chat, text: text, parse_mode: 'Markdown' },
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() >= 300) {
    throw new Error('Telegram ' + resp.getResponseCode() + ' — ' + resp.getContentText().slice(0, 200));
  }
}

// ---- 메인 ----
function run(force) {
  var owm = prop('OWM_API_KEY');
  if (!owm) throw new Error('스크립트 속성 OWM_API_KEY 가 비어 있음');
  var lat = prop('HOME_LAT', '37.6018');
  var lon = prop('HOME_LON', '127.0537');
  var label = prop('HOME_LABEL', '이문동');
  var quiet = (prop('QUIET_MODE', 'true').toLowerCase() !== 'false') && !force;

  var weatherSlots = filterTomorrow(fetchForecast(lat, lon, owm).list);
  if (!weatherSlots.length) { sendTelegram('⚠️ 내일 예보 데이터를 가져오지 못했어요.'); return; }

  var w = summarizeWeather(weatherSlots);
  var air = summarizeAir(filterTomorrow(fetchAir(lat, lon, owm).list));
  var pollen = summarizePollen(fetchPollen(lat, lon, prop('TOMORROW_API_KEY', '')));

  var store = PropertiesService.getScriptProperties();
  var t = tomorrowWindow();
  var todayKey = new Date(Date.now() + KST_MS).toISOString().slice(0, 10);
  var cached = JSON.parse(store.getProperty('_lastForecast') || 'null');
  var todayMax = (cached && cached.forDate === todayKey) ? cached.feelsMax : null;
  store.setProperty('_lastForecast', JSON.stringify({
    forDate: new Date(t.startMs + KST_MS).toISOString().slice(0, 10),
    feelsMax: w.feelsMax
  }));

  if (quiet && isRoutineDay(w, air, pollen, todayMax)) {
    Logger.log('평범한 날이라 알림 생략');
    return;
  }
  var msg = buildMessage(w, air, pollen, label, todayMax);
  sendTelegram(msg);
  Logger.log(msg);
}

// 매일 트리거가 호출하는 함수
function dailyWeather() { run(false); }

// 테스트: 평범한 날이어도 강제로 즉시 발송
function testSend() { run(true); }

// 매일 21:00(KST) + 05:40(KST) 자동 실행 트리거 설치 (한 번만 실행)
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (tr) {
    var fn = tr.getHandlerFunction();
    if (fn === 'dailyWeather' || fn === 'morningRainCheck') ScriptApp.deleteTrigger(tr);
  });
  ScriptApp.newTrigger('dailyWeather')
    .timeBased().everyDays(1).atHour(21)
    .inTimezone('Asia/Seoul').create();
  ScriptApp.newTrigger('morningRainCheck')
    .timeBased().everyDays(1).atHour(5).nearMinute(40)
    .inTimezone('Asia/Seoul').create();
  Logger.log('트리거 설치 완료: 매일 21:00 (내일 예보) + 매일 05:40 (비 오면 우산 리마인더)');
}

// 매일 아침 — 오늘 비 예보가 확실히 있을 때만 우산 리마인더 한 번 더 발송
function morningRainCheck() {
  var owm = prop('OWM_API_KEY');
  if (!owm) return;
  var lat = prop('HOME_LAT', '37.6018');
  var lon = prop('HOME_LON', '127.0537');
  var win = todayRestWindow();
  var slots = filterWindow(fetchForecast(lat, lon, owm).list, win);
  var w = summarizeWeather(slots);
  if (!w.rainSlots.length) {
    Logger.log('아침 우산 알림 생략 — 비 예보 없음');
    return;
  }
  sendTelegram('☔️☔️☔️우산 잊지 않으셨죠?');
}

// 테스트용 — 비 여부 상관없이 강제로 아침 리마인더 발송
function testMorning() {
  sendTelegram('☔️☔️☔️우산 잊지 않으셨죠?');
}

// 자기소개 메시지를 보내고 채팅에 고정한다 (한 번만 실행)
function pinIntro() {
  var token = prop('TELEGRAM_TOKEN');
  var chat = prop('TELEGRAM_CHAT_ID');
  if (!token || !chat) throw new Error('TELEGRAM_TOKEN / TELEGRAM_CHAT_ID 가 비어 있음');

  var intro = [
    '🌦 *웨더 리포트* — Weather Report',
    '',
    '기억은 잃었으나 하늘을 읽는 법은 남아 있다.',
    '매일 저녁 9시, 너에게 내일의 공기를 전한다.',
    '',
    '비도 바람도 먼지도 — 같은 흐름의 한 조각일 뿐.',
    '조용한 날엔 침묵하겠다. 그 또한 날씨다.'
  ].join('\n');

  var send = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
    method: 'post',
    payload: { chat_id: chat, text: intro, parse_mode: 'Markdown' },
    muteHttpExceptions: true
  });
  if (send.getResponseCode() >= 300) {
    throw new Error('sendMessage 실패 — ' + send.getContentText().slice(0, 300));
  }
  var msgId = JSON.parse(send.getContentText()).result.message_id;

  var pin = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/pinChatMessage', {
    method: 'post',
    payload: { chat_id: chat, message_id: msgId, disable_notification: 'true' },
    muteHttpExceptions: true
  });
  if (pin.getResponseCode() >= 300) {
    throw new Error('pinChatMessage 실패 — ' + pin.getContentText().slice(0, 300));
  }
  Logger.log('자기소개 전송 + 고정 완료 (message_id=' + msgId + ')');
}

// ============================================================
// 인터랙티브 — 텔레그램에서 봇에게 말 걸면 즉시 응답
// ============================================================

// 텔레그램이 새 메시지를 알려줄 때 호출됨 (웹훅 엔드포인트)
function doPost(e) {
  try {
    var update = JSON.parse(e.postData.contents);
    var msg = update.message || update.edited_message;
    if (!msg || !msg.text) return ContentService.createTextOutput('ok');
    if (String(msg.chat.id) !== prop('TELEGRAM_CHAT_ID')) {
      return ContentService.createTextOutput('ok'); // 다른 사람 채팅은 무시
    }
    handleChat(msg.text);
  } catch (err) {
    Logger.log('doPost error: ' + err);
  }
  return ContentService.createTextOutput('ok');
}

function doGet() {
  return ContentService.createTextOutput('웨더 리포트는 깨어 있다.');
}

function handleChat(text) {
  var t = (text || '').toLowerCase().trim();
  if (/내일|tomorrow|tmrw|tmr/.test(t)) { run(true); return; }
  if (/오늘|today|지금|현재|now/.test(t)) { todayReport(); return; }
  if (/비|우산|rain|umbrella/.test(t)) { rainOnly(); return; }
  if (/미세|먼지|공기|pm|air/.test(t)) { airOnly(); return; }
  if (/도움|help|메뉴|menu|\?/.test(t)) {
    sendTelegram(
      '나에게 물을 수 있는 것:\n' +
      '• "내일"  — 내일의 공기\n' +
      '• "오늘"  — 오늘 남은 시간\n' +
      '• "비"    — 비 / 우산\n' +
      '• "미세먼지" — 대기질'
    );
    return;
  }
  sendTelegram('내가 읽는 것은 하늘뿐.\n"내일", "오늘", "비", "미세먼지" — 그 중에 답이 있다.');
}

function todayRestWindow() {
  var nowSec = Math.floor(Date.now() / 1000);
  var k = new Date(Date.now() + KST_MS);
  var endMs = Date.UTC(k.getUTCFullYear(), k.getUTCMonth(), k.getUTCDate() + 1, 0, 0, 0) - KST_MS;
  return { startSec: nowSec, endSec: endMs / 1000 };
}

function filterWindow(list, win) {
  return (list || []).filter(function (it) { return it.dt >= win.startSec && it.dt < win.endSec; });
}

function todayReport() {
  var owm = prop('OWM_API_KEY');
  if (!owm) { sendTelegram('OWM 키가 없다.'); return; }
  var lat = prop('HOME_LAT', '37.6018');
  var lon = prop('HOME_LON', '127.0537');
  var label = prop('HOME_LABEL', '이문동');
  var win = todayRestWindow();
  var slots = filterWindow(fetchForecast(lat, lon, owm).list, win);
  if (!slots.length) { sendTelegram('🌙 오늘은 더 이상 예보가 없다. 내일을 물으라.'); return; }
  var w = summarizeWeather(slots);
  var air = summarizeAir(filterWindow(fetchAir(lat, lon, owm).list, win));
  var k = new Date(Date.now() + KST_MS);
  var header = '🗓 *오늘 (' + WEEKDAYS[k.getUTCDay()] + ') 남은 시간* ' + label;
  var feels = (w.feelsMin !== null) ?
    '체감 ' + Math.round(w.feelsMin) + '~' + Math.round(w.feelsMax) + '°C' : '';
  var lines = [header, '☁️ ' + w.flow + (feels ? ', ' + feels : '')];
  [umbrellaLine(w), airLine(air)].forEach(function (l) { if (l) lines.push(l); });
  sendTelegram(lines.join('\n'));
}

function rainOnly() {
  var owm = prop('OWM_API_KEY');
  var lat = prop('HOME_LAT', '37.6018');
  var lon = prop('HOME_LON', '127.0537');
  var nowSec = Math.floor(Date.now() / 1000);
  var slots = filterWindow(fetchForecast(lat, lon, owm).list, { startSec: nowSec, endSec: nowSec + 24 * 3600 });
  if (!slots.length) { sendTelegram('하늘이 비어 있다.'); return; }
  var w = summarizeWeather(slots);
  sendTelegram(umbrellaLine(w) || '🌂 앞으로 24시간 — 비는 없다.');
}

function airOnly() {
  var owm = prop('OWM_API_KEY');
  var lat = prop('HOME_LAT', '37.6018');
  var lon = prop('HOME_LON', '127.0537');
  var nowSec = Math.floor(Date.now() / 1000);
  var slots = filterWindow(fetchAir(lat, lon, owm).list, { startSec: nowSec, endSec: nowSec + 24 * 3600 });
  var s = summarizeAir(slots);
  if (!s) { sendTelegram('대기 데이터가 없다.'); return; }
  sendTelegram(airLine(s) || '😷 미세먼지 ' + s.grade + ' (' + Math.round(s.pm25Max) + ')');
}

// 웹 앱 배포한 뒤 한 번만 실행 — 텔레그램에 이 스크립트 URL을 webhook으로 등록
function installWebhook() {
  var url = ScriptApp.getService().getUrl();
  if (!url) throw new Error('먼저 "배포 → 새 배포 → 웹 앱"으로 배포해야 함');
  var token = prop('TELEGRAM_TOKEN');
  var resp = UrlFetchApp.fetch(
    'https://api.telegram.org/bot' + token + '/setWebhook?url=' + encodeURIComponent(url),
    { muteHttpExceptions: true }
  );
  Logger.log('웹훅 설정 URL: ' + url);
  Logger.log('응답: ' + resp.getContentText());
}

function removeWebhook() {
  var token = prop('TELEGRAM_TOKEN');
  var r = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/deleteWebhook', { muteHttpExceptions: true });
  Logger.log('웹훅 제거 응답: ' + r.getContentText());
}
