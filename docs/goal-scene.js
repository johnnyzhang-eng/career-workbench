/* A replaceable illustrated room renderer for the local goal companion.
 * No remote assets, personal data, activity inference, or business writes.
 */
(() => {
  'use strict';

  const sceneNonce = document.currentScript?.nonce || '';
  const modes = new Set(['idle', 'desk', 'study', 'interview', 'rest']);
  const phases = new Set(['day', 'evening']);
  const descriptions = {
    idle: '人物在房间里自然待机，等待本人选择行动',
    desk: '人物在书桌前处理任务',
    study: '人物在书桌前翻看练习材料',
    interview: '人物在书桌前做面试准备',
    rest: '人物在椅子上休息',
  };

  const css = `
    :host {
      --scene-hair: #25374c;
      --scene-skin: #d99f77;
      --scene-skin-shadow: #b9785c;
      --scene-outfit: #4d7e81;
      --scene-outfit-dark: #32666a;
      display: block;
      position: relative;
      width: 100%;
      min-width: 0;
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border-radius: 18px;
      background: #1c2f43;
      box-shadow: 0 13px 32px rgba(22, 44, 62, .16), inset 0 0 0 1px rgba(255,255,255,.2);
    }
    .scene-stage { position: absolute; inset: 0; width: 100%; height: 100%; }
    :host([avatar="student"]), :host(:not([avatar])) { --scene-hair: #25374c; --scene-skin: #d99f77; --scene-skin-shadow: #b9785c; --scene-outfit: #4d7e81; --scene-outfit-dark: #32666a; }
    :host([avatar="indigo"]) { --scene-hair: #202c44; --scene-skin: #ba826a; --scene-skin-shadow: #955d50; --scene-outfit: #7379a9; --scene-outfit-dark: #545b8e; }
    :host([avatar="amber"]) { --scene-hair: #5d3f32; --scene-skin: #e4b48c; --scene-skin-shadow: #c88e6b; --scene-outfit: #b47750; --scene-outfit-dark: #8c593f; }
    :host([avatar="plum"]) { --scene-hair: #49324a; --scene-skin: #8e5d52; --scene-skin-shadow: #70483f; --scene-outfit: #936b82; --scene-outfit-dark: #74556b; }
    svg { display: block; width: 100%; height: 100%; overflow: hidden; }
    .quiet-stroke { stroke: #253d50; stroke-width: 3.2; stroke-linejoin: round; stroke-linecap: round; }
    .hair { fill: var(--scene-hair); }
    .skin { fill: var(--scene-skin); }
    .skin-shadow { fill: var(--scene-skin-shadow); }
    .outfit { fill: var(--scene-outfit); }
    .outfit-dark { fill: var(--scene-outfit-dark); }
    .only-idle, .only-desk, .only-study, .only-interview, .only-rest,
    .sky-evening, .evening-glow { opacity: 0; pointer-events: none; }
    [data-mode="idle"] .only-idle,
    [data-mode="desk"] .only-desk,
    [data-mode="study"] .only-study,
    [data-mode="interview"] .only-interview,
    [data-mode="rest"] .only-rest,
    [data-phase="evening"] .sky-evening,
    [data-phase="evening"] .evening-glow { opacity: 1; }
    [data-phase="evening"] .sky-day, [data-phase="evening"] .day-beam { opacity: 0; }
    .soft-shift, .sky-day, .sky-evening, .evening-glow, .day-beam { transition: opacity .6s ease; }
    .eye-line { transform-origin: center; }
    .breath { transform-origin: 416px 263px; }
    .screen-glow { opacity: .48; }
    .scene-edge { fill: none; stroke: rgba(246, 229, 199, .24); stroke-width: 2; }
    .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    svg[hidden], .pixel-stage[hidden], .pixel-stage img[hidden] { display: none !important; }
    [data-mode="rest"] .seated-avatar { opacity: 0; }
    .pixel-stage { position: relative; width: 100%; height: 100%; background: #1c2f43; overflow: hidden; }
    .pixel-stage img { position: absolute; display: block; image-rendering: pixelated; image-rendering: crisp-edges; pointer-events: none; user-select: none; }
    .pixel-bg { inset: 0; width: 100%; height: 100%; object-fit: fill; }
    .pixel-desk-front { inset: 0; width: 100%; height: 100%; object-fit: fill; }
    .pixel-avatar { width: 28%; height: 63%; left: 36%; bottom: 9%; object-fit: contain; object-position: center bottom; }
    .pixel-stage[data-mode="desk"] .pixel-avatar,
    .pixel-stage[data-mode="study"] .pixel-avatar,
    .pixel-stage[data-mode="interview"] .pixel-avatar { width: 29%; height: 65%; left: 39%; bottom: 17%; }
    .pixel-stage[data-mode="rest"] .pixel-avatar { width: 30%; height: 62%; left: 69%; bottom: 7%; }
    @media (max-width: 380px) { :host { border-radius: 12px; box-shadow: 0 8px 18px rgba(22,44,62,.15); } }
    @media (prefers-reduced-motion: no-preference) {
      .breath { animation: breathe 4.8s ease-in-out infinite; }
      .eye-line { animation: blink 6.4s step-end infinite; }
      .lamp-halo { animation: lamplight 5s ease-in-out infinite; }
      .sparkle { animation: drift 3.9s ease-in-out infinite alternate; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
    }
    @keyframes breathe { 0%,100% { transform: translateY(0); } 50% { transform: translateY(1.8px); } }
    @keyframes blink { 0%,95%,100% { transform: scaleY(1); } 96%,98% { transform: scaleY(.16); } }
    @keyframes lamplight { 0%,100% { opacity: .72; } 50% { opacity: .9; } }
    @keyframes drift { from { transform: translateY(0); opacity: .6; } to { transform: translateY(-5px); opacity: 1; } }
  `;

  const markup = `
    <svg viewBox="0 0 800 450" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
      <title id="room-title">目标房间</title>
      <desc id="room-desc">人物在房间里自然待机</desc>
      <defs>
        <linearGradient id="room-wall" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#57768d"/><stop offset="1" stop-color="#6d8290"/></linearGradient>
        <linearGradient id="room-floor" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#b78b67"/><stop offset=".55" stop-color="#9a735c"/><stop offset="1" stop-color="#795c53"/></linearGradient>
        <linearGradient id="sky-day" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#9ed1dd"/><stop offset=".65" stop-color="#d9e7dc"/><stop offset="1" stop-color="#f6d8ab"/></linearGradient>
        <linearGradient id="sky-evening" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#344e7e"/><stop offset=".62" stop-color="#bd817c"/><stop offset="1" stop-color="#edb479"/></linearGradient>
        <linearGradient id="desk-wood" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#e6bb87"/><stop offset=".55" stop-color="#bd865b"/><stop offset="1" stop-color="#a36d4e"/></linearGradient>
        <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#8ec8c5"/><stop offset="1" stop-color="#486d83"/></linearGradient>
        <radialGradient id="lamp-light"><stop stop-color="#ffeab1" stop-opacity=".72"/><stop offset="1" stop-color="#ffdb8c" stop-opacity="0"/></radialGradient>
        <radialGradient id="vignette"><stop offset=".58" stop-color="#0d263a" stop-opacity="0"/><stop offset="1" stop-color="#0d263a" stop-opacity=".36"/></radialGradient>
        <filter id="soft-shadow" x="-35%" y="-35%" width="170%" height="170%"><feGaussianBlur stdDeviation="7"/></filter>
        <clipPath id="window-clip"><rect x="138" y="66" width="208" height="135" rx="8"/></clipPath>
      </defs>

      <rect width="800" height="450" rx="22" fill="#1b3045"/>
      <path d="M73 30 698 30 762 75 751 315 589 430 184 430 39 306 39 68Z" fill="#273e50"/>
      <path d="M76 35H699L715 265H76Z" fill="url(#room-wall)"/>
      <path d="M39 68 76 35V265L39 304Z" fill="#355469"/>
      <path d="M699 35 761 75 751 313 715 265Z" fill="#324d60"/>
      <path d="M76 265H715L751 313 589 428H184L39 304Z" fill="url(#room-floor)"/>
      <path d="M76 265H715M76 272 39 310M715 272 751 317" fill="none" stroke="#e3bd8e" stroke-width="5" opacity=".75"/>
      <path d="M133 298 193 428M298 268 316 428M468 268 447 428M618 270 548 428M41 335 747 335M95 376 673 376" stroke="#775b54" stroke-width="2" opacity=".22"/>
      <path d="M223 325 579 325 623 361 547 405 242 405 181 366Z" fill="#e2bc8a" opacity=".7"/>
      <path d="M228 330 575 330 611 360 541 397 248 397 195 366Z" fill="#c78365" opacity=".54"/>
      <path d="M236 337 563 337 590 358 533 386 259 386 218 364Z" fill="none" stroke="#f1d1a6" stroke-width="3" opacity=".66"/>

      <!-- Window: one real-world phase changes the light, not the task truth. -->
      <g clip-path="url(#window-clip)">
        <rect x="138" y="66" width="208" height="135" fill="url(#sky-day)" class="sky-day"/>
        <rect x="138" y="66" width="208" height="135" fill="url(#sky-evening)" class="sky-evening"/>
        <circle cx="295" cy="91" r="17" fill="#fff0c4" class="sky-day" opacity=".88"/>
        <circle cx="293" cy="94" r="11" fill="#f9deb2" class="sky-evening"/>
        <path d="M138 171 159 150 184 168 211 146 237 165 264 146 291 161 319 146 346 166V210H138Z" fill="#77929b" opacity=".42"/>
        <path d="M138 184 158 180V162H169V178H178V156H192V181H207V170H224V185H242V159H254V185H265V169H284V185H301V164H319V182H346V210H138Z" fill="#4e7481" opacity=".66"/>
        <path d="M144 204c17-20 32-15 40-5 17-24 35-17 44-5 23-25 45-18 55 0 19-22 39-18 63 0v19H144Z" fill="#607260"/>
        <path d="M155 202q-3-24 2-39m13 39q3-28 10-41m103 43q-1-24 4-41m13 40q4-25 9-42" stroke="#725d55" stroke-width="4"/>
        <g fill="#cb855b"><circle cx="154" cy="166" r="15"/><circle cx="173" cy="164" r="16"/><circle cx="287" cy="165" r="16"/><circle cx="307" cy="166" r="15"/></g>
        <g fill="#e6ae70"><circle cx="166" cy="159" r="11"/><circle cx="298" cy="155" r="12"/></g>
      </g>
      <rect x="130" y="58" width="224" height="151" rx="10" fill="none" stroke="#e5d8bb" stroke-width="11"/>
      <path d="M242 61V205M134 136H350" stroke="#e5d8bb" stroke-width="8"/>
      <path d="M128 212H355" stroke="#354d59" stroke-width="11" stroke-linecap="round" opacity=".45"/>
      <path class="day-beam soft-shift" d="M142 205 322 205 507 315 262 315Z" fill="#fbe2a7" opacity=".16"/>

      <!-- Notice board, shelf and domestic details stay legible at 320px. -->
      <path d="M578 70 673 70 679 179 580 184Z" fill="#d2b48e" stroke="#3a5260" stroke-width="7" stroke-linejoin="round"/>
      <path d="M591 85 625 82 628 124 593 126Z" fill="#f3e2c8" transform="rotate(-4 609 105)"/>
      <path d="M632 91 662 96 658 132 629 128Z" fill="#f4cc9b" transform="rotate(5 645 110)"/>
      <path d="M600 136 654 133 655 164 600 165Z" fill="#c5d9d1" transform="rotate(-3 628 150)"/>
      <circle cx="611" cy="90" r="3" fill="#a65d47"/><circle cx="648" cy="94" r="3" fill="#a65d47"/><circle cx="626" cy="137" r="3" fill="#a65d47"/>
      <path d="M602 105h17m-18 7h13m21-8h17m-15 7h15m-41 37h36" stroke="#9f9b87" stroke-width="2" stroke-linecap="round" opacity=".68"/>
      <path d="M88 209h185v12H88Z" fill="#d1a77b" stroke="#355061" stroke-width="4"/>
      <path d="M104 197v-27h14v27m2 0v-34h13v34m3 0v-30h13v30m5 0v-23h12v23" stroke="#3c6172" stroke-width="11" stroke-linecap="round"/>
      <path d="M108 182h6m9-7h6m11 7h5" stroke="#e7c387" stroke-width="2"/>
      <path d="M189 199 177 187 186 174 201 180 202 198Z" fill="#b86d55"/>
      <path d="M210 200h35l-4-7h-28Z" fill="#b4b496"/>
      <path d="M221 192q-17-15-5-29m7 30q1-29 16-39m-11 39q12-22 26-17" fill="none" stroke="#3e6e64" stroke-width="5" stroke-linecap="round"/>
      <g fill="#689579"><ellipse cx="215" cy="161" rx="8" ry="15" transform="rotate(-26 215 161)"/><ellipse cx="243" cy="154" rx="10" ry="15" transform="rotate(23 243 154)"/><ellipse cx="252" cy="175" rx="11" ry="7" transform="rotate(-24 252 175)"/></g>

      <!-- A quiet rest chair remains part of the room in every mode. -->
      <ellipse cx="664" cy="371" rx="74" ry="16" fill="#3e4b4b" opacity=".22" filter="url(#soft-shadow)"/>
      <path d="M611 249q-2-25 19-28h58q22 3 22 29v73q-5 22-28 25h-47q-23-5-25-26Z" fill="#9f6859" stroke="#334959" stroke-width="6"/>
      <path d="M625 254q1-15 15-16h39q16 2 16 18v58q-4 13-18 14h-36q-15-1-17-15Z" fill="#d99a75"/>
      <path d="M617 310q-16 0-16 18 1 16 21 18h77q20-3 21-19-2-16-17-17Z" fill="#a96e5e" stroke="#334959" stroke-width="5"/>
      <path d="M627 342v27m67-28v28" stroke="#354b55" stroke-width="9" stroke-linecap="round"/>
      <path d="M697 273q13-8 25 5l-5 28q-12 11-22 4" fill="#9f6859" stroke="#334959" stroke-width="5"/>
      <path d="M591 334q-15 0-18 14l8 20h33l6-19q-5-17-29-15Z" fill="#b7a38a" stroke="#334959" stroke-width="4"/>
      <path d="M583 340q-6-34 12-61m2 61q17-32 25-49m-26 48q-23-13-27-38" stroke="#406d65" stroke-width="5" stroke-linecap="round" fill="none"/>
      <g fill="#6c9878"><ellipse cx="591" cy="286" rx="12" ry="21" transform="rotate(-18 591 286)"/><ellipse cx="616" cy="294" rx="12" ry="19" transform="rotate(27 616 294)"/><ellipse cx="571" cy="301" rx="11" ry="18" transform="rotate(-43 571 301)"/></g>

      <!-- Desk, chair and avatar have separate layers to preserve silhouette. -->
      <ellipse cx="414" cy="345" rx="218" ry="34" fill="#26384a" opacity=".24" filter="url(#soft-shadow)"/>
      <path d="M331 234q0-23 22-28h81q25 4 28 28v101h-133Z" fill="#607986" stroke="#2d4555" stroke-width="6"/>
      <path d="M344 226q5-9 17-9h65q13 0 19 10v85h-101Z" fill="#8ba1a4"/>
      <path d="M350 311h96v23h-96Z" fill="#506b78"/>

      <!-- Sitting figure: expression and forearms change, no score metaphors. -->
      <g class="breath seated-avatar">
        <path d="M368 270q2-41 26-49h37q32 8 39 49l-7 42h-105Z" class="outfit quiet-stroke"/>
        <path d="M396 222q-3 19 18 23 22-3 20-23" class="skin-shadow"/>
        <path d="M397 219 414 245 432 220" fill="#f7e7d0"/>
        <path d="M392 223 411 246 399 259 382 232m51-9-20 23 12 13 20-26" class="outfit-dark" opacity=".65"/>
        <path d="M368 261q-11-4-21 12l-7 26 29 9 17-32" class="outfit quiet-stroke"/>
        <path d="M454 263q15-2 20 13l11 29-26 7-19-33" class="outfit quiet-stroke"/>
        <path d="M386 220q-16-22-10-42 1-38 37-46 43 0 46 44 4 27-14 47Z" class="hair quiet-stroke"/>
        <ellipse cx="414" cy="185" rx="35" ry="42" class="skin quiet-stroke"/>
        <path d="M380 176q-4-31 20-42 27-10 49 8 10 10 10 29-15-8-20-24-13 20-42 19-6 8-17 10Z" class="hair"/>
        <path d="M389 165q3-15 19-19m29 2q8 8 12 20" fill="none" stroke="#536275" stroke-width="3" opacity=".45"/>
        <ellipse cx="381" cy="188" rx="7" ry="11" class="skin-shadow"/>
        <ellipse cx="448" cy="188" rx="7" ry="11" class="skin-shadow"/>
        <g class="eye-line" fill="#293a4a"><ellipse cx="400" cy="186" rx="2.8" ry="3.6"/><ellipse cx="429" cy="186" rx="2.8" ry="3.6"/></g>
        <path d="M396 175q5-3 11-1m17 0q6-2 11 1" fill="none" stroke="#42505b" stroke-width="2.4" stroke-linecap="round"/>
        <path d="M407 204q8 5 16-1" fill="none" stroke="#995b57" stroke-width="2.4" stroke-linecap="round"/>
        <path d="M396 197q-2 6-8 2m48-2q3 6 8 2" fill="none" stroke="#c47e70" stroke-width="2" opacity=".6"/>
        <g class="only-study soft-shift">
          <path d="M376 179q-3-35 35-47 46-1 47 48" fill="none" stroke="#d4ad70" stroke-width="8" stroke-linecap="round"/>
          <rect x="371" y="181" width="11" height="29" rx="5" fill="#ebc78d"/>
          <rect x="447" y="181" width="11" height="29" rx="5" fill="#ebc78d"/>
        </g>
        <g class="only-interview soft-shift">
          <path d="M398 225 414 244 431 224 429 254 414 270 399 254Z" fill="#f1e6dc"/>
          <path d="M413 244 418 244 422 265 414 275 407 266Z" fill="#d1a16a"/>
          <path d="M373 183q0-42 41-48 43 2 44 48" fill="none" stroke="#d6bc9c" stroke-width="5"/>
          <path d="M448 198q10 4 9 13l-15 3" fill="none" stroke="#d6bc9c" stroke-width="4" stroke-linecap="round"/>
          <circle cx="440" cy="214" r="4" fill="#d6bc9c"/>
        </g>
      </g>

      <!-- Isometric work surface and grounded objects. -->
      <path d="M276 276 531 276 617 300 535 323 289 321 218 297Z" fill="url(#desk-wood)" stroke="#4b4f50" stroke-width="5" stroke-linejoin="round"/>
      <path d="M218 297 289 321 535 323 617 300 612 312 537 336 288 333 218 307Z" fill="#986948" stroke="#4b4f50" stroke-width="4"/>
      <path d="M274 327 290 331 283 392 261 390Zm316-6 21-7 17 65-20 7Z" fill="#785447" stroke="#4b4f50" stroke-width="4"/>
      <path d="M228 295 277 276M534 276 605 299" fill="none" stroke="#f4d5a4" stroke-width="3" opacity=".75"/>
      <g class="only-desk only-interview soft-shift">
        <path d="M477 215q0-10 10-11h115q9 1 10 11l-6 75H481Z" fill="#344d5e" stroke="#233a4b" stroke-width="5"/>
        <path d="M490 216h108l-4 61H494Z" fill="url(#screen)"/>
        <path d="M481 285h124l24 13-25 7H467l-12-7Z" fill="#bcc5c0" stroke="#344c5a" stroke-width="4"/>
        <path d="M497 291h98m-86 5h75" stroke="#71898f" stroke-width="2"/>
        <circle cx="545" cy="210" r="2.8" fill="#d6dccf"/>
        <g class="only-desk soft-shift"><rect x="509" y="235" width="72" height="6" rx="3" fill="#f4e6c9" opacity=".9"/><rect x="509" y="249" width="52" height="5" rx="2.5" fill="#d7e2d9" opacity=".8"/><rect x="509" y="261" width="64" height="4" rx="2" fill="#c1d4d2" opacity=".62"/></g>
        <g class="only-interview soft-shift"><circle cx="545" cy="247" r="20" fill="#d8d3bc" opacity=".68"/><circle cx="545" cy="241" r="7" fill="#506b74"/><path d="M531 258q5-11 14-11 12 0 15 11" fill="#506b74"/><path d="M572 234h15m-14 8h13m-10 8h10" stroke="#e1e7dc" stroke-width="3" stroke-linecap="round"/></g>
      </g>
      <g class="only-study soft-shift">
        <path d="M473 282q26-17 52 1 26-18 54-1l9 22q-37-13-64 5-32-19-64-5Z" fill="#f1e4c9" stroke="#546576" stroke-width="4" stroke-linejoin="round"/>
        <path d="M525 283v25m-51-21q21-7 42 3m-38 5q18-6 38 3m17-8q20-12 40-5m-39 14q20-12 40-7" stroke="#bdab8e" stroke-width="2" stroke-linecap="round" fill="none"/>
        <path d="M582 266 589 267 579 309 572 307Z" fill="#ddb875" stroke="#6e6e62" stroke-width="2"/>
        <path d="M579 309 572 307 574 315Z" fill="#4e5662"/>
      </g>
      <g class="only-idle soft-shift"><path d="M503 282h59l9 20-75 1Z" fill="#849ca1" stroke="#435665" stroke-width="4"/><path d="M520 282v-8h24v8" fill="#566f7c"/><path d="M551 286q7-16 15-12 8 7-3 20" fill="none" stroke="#eed5aa" stroke-width="5"/></g>
      <g class="only-rest soft-shift"><path d="M505 287h50l9 16-67 1Z" fill="#677e89" stroke="#435665" stroke-width="4"/><path d="M515 287v-6h28v6" fill="#3c5b67"/></g>
      <g class="only-desk soft-shift"><path d="M461 298q6-9 15-7l11 7-7 7-16-3Z" class="skin quiet-stroke"/><path d="M407 302q8-8 17-6l13 7-4 8-23-2Z" class="skin quiet-stroke"/></g>
      <g class="only-study soft-shift"><path d="M452 295q8-6 17-2l9 8-6 8-18-5Z" class="skin quiet-stroke"/><path d="M413 293q8-7 17-3l10 8-6 7-20-4Z" class="skin quiet-stroke"/></g>
      <g class="only-interview soft-shift"><path d="M442 296q9-9 20-5l13 11-6 10-20-5Z" class="skin quiet-stroke"/><path d="M412 300q9-7 17-3l14 9-8 9-20-7Z" class="skin quiet-stroke"/></g>
      <g class="only-idle soft-shift"><path d="M401 300q5-10 15-8l15 13-7 8-19-3Z" class="skin quiet-stroke"/></g>
      <g class="only-rest soft-shift"><path d="M401 302q10-8 19-6l12 12-10 8-20-6Z" class="skin quiet-stroke"/></g>

      <!-- A lamp switches the room from window-lit to lamplit in the evening. -->
      <ellipse class="evening-glow lamp-halo" cx="306" cy="274" rx="94" ry="70" fill="url(#lamp-light)"/>
      <path d="M304 286v-62l-17-22m18 84h-20m28-61-26-23" stroke="#4e5d61" stroke-width="6" stroke-linecap="round"/>
      <path d="M266 197q11-21 36-7l5 16-29 14Z" fill="#efc983" stroke="#4b5961" stroke-width="4" stroke-linejoin="round"/>
      <ellipse cx="281" cy="211" rx="11" ry="4" fill="#fff3c9" opacity=".85"/>
      <ellipse cx="308" cy="288" rx="25" ry="6" fill="#485b5f" opacity=".6"/>
      <g class="only-study soft-shift"><circle class="sparkle" cx="561" cy="222" r="3" fill="#ffdc9a"/><circle class="sparkle" cx="582" cy="213" r="2" fill="#ffdc9a"/></g>

      <!-- Rest state moves the person into the chair; the desk figure fades out. -->
      <g class="only-rest soft-shift">
        <path d="M647 319q-22-9-18-35 7-27 31-27 26 4 33 30l-6 35Z" class="outfit quiet-stroke"/>
        <path d="M638 281q-11-4-19 11l-9 12 22 10 13-20" class="outfit quiet-stroke"/>
        <ellipse cx="665" cy="250" rx="24" ry="29" class="skin quiet-stroke"/>
        <path d="M642 244q-2-21 15-26 25-7 32 17-10 0-16-10-14 14-31 19Z" class="hair"/>
        <path d="M655 251h4m15 0h4" stroke="#354150" stroke-width="2.6" stroke-linecap="round"/>
        <path d="M659 265q6 4 12 0" stroke="#995b57" stroke-width="2" fill="none"/>
        <path d="M625 306q8 0 18 7l9-3" stroke="#a57459" stroke-width="9" stroke-linecap="round" fill="none"/>
        <path d="M705 297h19q8 0 5 10-4 12-15 12h-15Z" fill="#f1d7b0" stroke="#6a6260" stroke-width="3"/>
        <path d="M725 300q17-2 14 9-2 8-15 6" fill="none" stroke="#f1d7b0" stroke-width="5"/>
      </g>
      <g class="only-idle soft-shift"><path d="M648 288h17v28h-17Z" fill="#e4b890" opacity=".55"/></g>
      <rect width="800" height="450" rx="22" fill="url(#vignette)" pointer-events="none"/>
      <rect x="4" y="4" width="792" height="442" rx="19" class="scene-edge" pointer-events="none"/>
    </svg>`;

  function localPhase(timezone) {
    try {
      const hour = Number(new Intl.DateTimeFormat('en-GB', {
        timeZone: timezone || 'Asia/Shanghai', hour: '2-digit', hourCycle: 'h23',
      }).format(new Date()));
      return hour >= 6 && hour < 18 ? 'day' : 'evening';
    } catch (_) {
      return 'day';
    }
  }

  function localAsset(value) {
    // The server's /scene-assets route is an explicit allowlist. Do not
    // permit remote URLs, query parameters or traversal through user data.
    if (typeof value !== 'string' || !/^\/scene-assets\/[A-Za-z0-9_./-]+\.(png|webp)$/.test(value)
        || value.split('/').includes('..')) return null;
    return value;
  }

  class GoalRoomScene extends HTMLElement {
    static get observedAttributes() {
      return ['mode', 'phase', 'timezone', 'avatar', 'renderer', 'room-src',
              'room-day-src', 'room-evening-src', 'avatar-src', 'avatar-idle-src',
              'avatar-desk-src', 'avatar-study-src', 'avatar-interview-src', 'avatar-rest-src',
              'desk-front-src'];
    }

    constructor() {
      super();
      const root = this.attachShadow({mode: 'open'});
      const style = document.createElement('style');
      if (sceneNonce) style.nonce = sceneNonce;
      style.textContent = css;
      root.append(style);
      const stage = document.createElement('div');
      stage.className = 'scene-stage';
      stage.innerHTML = markup;
      const pixel = document.createElement('div');
      pixel.className = 'pixel-stage';
      pixel.hidden = true;
      const background = document.createElement('img');
      background.className = 'pixel-bg';
      background.alt = '';
      background.setAttribute('aria-hidden', 'true');
      const avatar = document.createElement('img');
      avatar.className = 'pixel-avatar';
      avatar.alt = '';
      avatar.setAttribute('aria-hidden', 'true');
      const deskFront = document.createElement('img');
      deskFront.className = 'pixel-desk-front';
      deskFront.alt = '';
      deskFront.hidden = true;
      deskFront.setAttribute('aria-hidden', 'true');
      pixel.append(background, avatar, deskFront);
      stage.append(pixel);
      root.append(stage);
      this._svg = stage.querySelector('svg');
      this._desc = stage.querySelector('#room-desc');
      this._pixel = pixel;
      this._pixelBg = background;
      this._pixelAvatar = avatar;
      this._pixelDeskFront = deskFront;
      this._lastPhase = '';
      this._clockTimer = null;
      this._failedAssets = new Set();
      background.addEventListener('error', () => this._pixelFallback(background.getAttribute('src')));
      avatar.addEventListener('error', () => this._pixelFallback(avatar.getAttribute('src')));
      background.addEventListener('load', () => this._sync());
      avatar.addEventListener('load', () => this._sync());
      deskFront.addEventListener('load', () => this._sync());
      deskFront.addEventListener('error', () => {
        const failedSrc = deskFront.getAttribute('src');
        if (failedSrc) this._failedAssets.add(failedSrc);
        this._sync();
      });
    }

    connectedCallback() {
      this.setAttribute('role', 'img');
      this._sync();
      this._clockTimer = window.setInterval(() => {
        if (!phases.has(this.getAttribute('phase'))) this._sync();
      }, 60_000);
    }

    disconnectedCallback() {
      if (this._clockTimer !== null) window.clearInterval(this._clockTimer);
      this._clockTimer = null;
    }

    attributeChangedCallback() { this._sync(); }

    _pixelFallback(failedSrc) {
      if (failedSrc) this._failedAssets.add(failedSrc);
      this._pixel.hidden = true;
      this._svg.removeAttribute('hidden');
      this.setAttribute('data-scene-fallback', 'illustrated');
      this.setAttribute('aria-label', this._desc.textContent + '。像素素材尚未加载，当前显示插画草案');
    }

    _sync() {
      if (!this._svg) return;
      const requestedMode = this.getAttribute('mode');
      const mode = modes.has(requestedMode) ? requestedMode : 'idle';
      const requestedPhase = this.getAttribute('phase');
      const phase = phases.has(requestedPhase) ? requestedPhase : localPhase(this.getAttribute('timezone'));
      this._svg.dataset.mode = mode;
      this._svg.dataset.phase = phase;
      this._pixel.dataset.mode = mode;
      this._pixel.dataset.phase = phase;
      this._desc.textContent = descriptions[mode] + (phase === 'day' ? '，白天窗光' : '，傍晚暖灯');
      const room = localAsset(this.getAttribute(`room-${phase}-src`)) || localAsset(this.getAttribute('room-src'));
      const avatar = localAsset(this.getAttribute(`avatar-${mode}-src`)) || localAsset(this.getAttribute('avatar-src'));
      const bundledRoom = room === '/scene-assets/room-day.png' || room === '/scene-assets/room-evening.png';
      const deskFront = localAsset(this.getAttribute('desk-front-src'))
        || (bundledRoom ? '/scene-assets/desk-front.png' : null);
      const configured = this.getAttribute('renderer') === 'pixel' && room && avatar;
      if (configured && this._pixelBg.getAttribute('src') !== room) this._pixelBg.setAttribute('src', room);
      if (configured && this._pixelAvatar.getAttribute('src') !== avatar) this._pixelAvatar.setAttribute('src', avatar);
      if (configured && deskFront && this._pixelDeskFront.getAttribute('src') !== deskFront) {
        this._pixelDeskFront.setAttribute('src', deskFront);
      }
      const frontReady = deskFront && !this._failedAssets.has(deskFront)
        && this._pixelDeskFront.complete && this._pixelDeskFront.naturalWidth > 0;
      this._pixelDeskFront.hidden = !(configured && frontReady
        && (mode === 'desk' || mode === 'study' || mode === 'interview'));
      const pixelReady = configured && !this._failedAssets.has(room) && !this._failedAssets.has(avatar)
        && this._pixelBg.complete && this._pixelAvatar.complete
        && this._pixelBg.naturalWidth > 0 && this._pixelAvatar.naturalWidth > 0;
      if (pixelReady) {
        this._pixel.hidden = false;
        this._svg.setAttribute('hidden', '');
        this.removeAttribute('data-scene-fallback');
      } else {
        this._pixel.hidden = true;
        this._svg.removeAttribute('hidden');
        if (this.getAttribute('renderer') === 'pixel') this.setAttribute('data-scene-fallback', 'illustrated');
        else this.removeAttribute('data-scene-fallback');
      }
      const fallback = this.hasAttribute('data-scene-fallback') ? '。当前显示插画草案' : '';
      this.setAttribute('aria-label', this._desc.textContent + fallback);
      this._lastPhase = phase;
    }
  }

  // Scene rendering does not infer an action from a plan. The host adapter
  // should supply mode only after an explicit start or trusted activity clue.
  function resolveMode(selected) {
    const mode = selected?.scene?.mode;
    return modes.has(mode) ? mode : 'idle';
  }

  if (!customElements.get('goal-room-scene')) customElements.define('goal-room-scene', GoalRoomScene);
  window.CareerGoalScene = Object.freeze({resolveMode, modes: Object.freeze([...modes])});
})();
