/*
 * Plain-JS versions of the React prototype's controls (vite_web/src/components).
 *
 * Each control is a front end for an ordinary form element that the simulation
 * code already reads by id. The simulation code never knows these exist: it
 * keeps reading `.value` and listening for "change", and the controls keep
 * those elements up to date.
 *
 *   <div class="slider" ...>      a range input with a label and live value
 *   <div class="button-row" ...>  buttons that drive a hidden <select>
 *   <div class="compass" ...>     a draggable wind arrow that writes "from" degrees
 *
 * References:
 *   https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dataset
 *   https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/dispatchEvent
 *   https://developer.mozilla.org/en-US/docs/Web/API/Element/setPointerCapture
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const COMPASS_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

// Tells the simulation code a value changed, the same way a real user edit would.
function announce(element) {
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

/*
 * Slider
 *
 * <div class="slider" data-unit=" mph" data-writes="sim-wind-speed" data-factor="0.44704">
 *   <div class="slider-top"><span>Wind speed</span><span class="slider-value"></span></div>
 *   <input type="range" min="0" max="50" value="11">
 * </div>
 *
 * data-unit:    text after the number in the label
 * data-writes:  optional id of another input to keep in sync, for when the
 *               slider shows friendlier units than the simulation code expects
 * data-factor:  multiplier from the slider's units to that input's units
 */
function setUpSlider(root) {
  const range = root.querySelector("input[type=range]");
  const label = root.querySelector(".slider-value");
  const unit = root.dataset.unit ?? "";
  const target = root.dataset.writes ? document.getElementById(root.dataset.writes) : null;
  const factor = Number(root.dataset.factor ?? 1);

  function sync() {
    label.textContent = `${range.value}${unit}`;
    if (target) {
      // One decimal is plenty, and keeps labels like "4.9 m/s" readable.
      target.value = Math.round(Number(range.value) * factor * 10) / 10;
      announce(target);
    }
  }
  range.addEventListener("input", sync);
  sync();
}

/*
 * Button group
 *
 * <div class="button-row" data-for="sim-hours"></div>
 * <select id="sim-hours" hidden> <option value="1">1 hour</option> ... </select>
 *
 * Builds one button per <option>, using data-label on the option when it has
 * one (for shorter text), and keeps the select's value in sync.
 */
function setUpButtonGroup(root) {
  const select = document.getElementById(root.dataset.for);
  select.hidden = true;

  const buttons = [...select.options].map((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "option";
    button.textContent = option.dataset.label ?? option.textContent;
    button.addEventListener("click", () => {
      select.value = option.value;
      announce(select);
    });
    root.append(button);
    return { button, option };
  });

  function sync() {
    for (const { button, option } of buttons) {
      const isSelected = option.value === select.value;
      button.classList.toggle("selected", isSelected);
      button.setAttribute("aria-pressed", isSelected);
    }
  }
  select.addEventListener("change", sync);
  sync();
}

/*
 * Compass
 *
 * <div class="compass" data-for="sim-wind-from"></div>
 * <input type="hidden" id="sim-wind-from" value="270">
 *
 * The arrow points where the wind blows TOWARD, which is how people picture a
 * fire being pushed. The input holds where it comes FROM, which is what weather
 * data and the backend use. The two are always 180 degrees apart.
 */
function setUpCompass(root) {
  const input = document.getElementById(root.dataset.for);

  const header = document.createElement("div");
  header.className = "slider-top";
  const title = document.createElement("span");
  title.textContent = root.dataset.label ?? "Wind direction";
  const readout = document.createElement("span");
  readout.className = "slider-value";
  header.append(title, readout);

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "-50 -50 100 100");
  svg.setAttribute("width", "100");
  svg.setAttribute("height", "100");
  svg.setAttribute("role", "slider");
  svg.setAttribute("aria-label", "Wind direction");
  svg.setAttribute("tabindex", "0");
  svg.innerHTML = `
    <circle r="44" class="compass-face" />
    <text y="-33" class="compass-label">N</text>
    <text x="34" class="compass-label">E</text>
    <text y="34" class="compass-label">S</text>
    <text x="-34" class="compass-label">W</text>
    <g class="compass-arrow">
      <line y1="18" y2="-22" stroke-width="3" stroke-linecap="round" />
      <polygon points="0,-30 -7,-19 7,-19" />
    </g>`;
  const arrow = svg.querySelector(".compass-arrow");
  root.append(header, svg);

  let toward = (Number(input.value) + 180) % 360;

  function draw() {
    arrow.setAttribute("transform", `rotate(${toward})`);
    const name = COMPASS_LABELS[Math.round(toward / 45) % 8];
    readout.textContent = `Toward ${name} (${toward}°)`;
    svg.setAttribute("aria-valuenow", toward);
  }

  function set(deg) {
    toward = ((Math.round(deg / 5) * 5) % 360 + 360) % 360;
    input.value = (toward + 180) % 360;
    announce(input);
    draw();
  }

  // Angle from the center of the dial to the pointer, with 0 at north.
  function fromPointer(event) {
    const box = svg.getBoundingClientRect();
    const dx = event.clientX - (box.left + box.width / 2);
    const dy = event.clientY - (box.top + box.height / 2);
    set((Math.atan2(dx, -dy) * 180) / Math.PI);
  }

  svg.addEventListener("pointerdown", (event) => {
    svg.setPointerCapture(event.pointerId);
    fromPointer(event);
  });
  svg.addEventListener("pointermove", (event) => {
    if (svg.hasPointerCapture(event.pointerId)) fromPointer(event);
  });
  // Arrow keys nudge it, so it works without a mouse.
  svg.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowUp") set(toward + 15);
    else if (event.key === "ArrowLeft" || event.key === "ArrowDown") set(toward - 15);
    else return;
    event.preventDefault();
  });

  draw();
}

document.querySelectorAll(".slider").forEach(setUpSlider);
document.querySelectorAll(".button-row[data-for]").forEach(setUpButtonGroup);
document.querySelectorAll(".compass[data-for]").forEach(setUpCompass);
